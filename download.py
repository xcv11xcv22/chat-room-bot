from huggingface_hub import hf_hub_download
import os
import time

def download_file_with_retry(repo_id, filename, local_dir, max_retries=3, wait_seconds=5):
    """下載單個檔案，支援自動重試"""
    for attempt in range(1, max_retries + 1):
        try:
            print(f"正在下載 (第 {attempt} 次) {filename} ...")
            file_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=local_dir,
                cache_dir=local_dir,
            )
            print(f"成功下載 {filename} 至 {file_path}")
            return file_path
        except Exception as e:
            print(f"第 {attempt} 次下載 {filename} 失敗：{e}")
            if attempt < max_retries:
                print(f"等待 {wait_seconds} 秒後重試...")
                time.sleep(wait_seconds)
            else:
                print(f"已重試 {max_retries} 次仍失敗，放棄下載 {filename}")
                return None

def download():
    repo_id = "Bard504/llama3_ptt_1b"
    model_dir = "model"
    os.makedirs(model_dir, exist_ok=True)

    # 如果合併後的 model.safetensors 已存在，則跳過下載
    merged_model_path = os.path.join(model_dir, "model.safetensors")
    if os.path.exists(merged_model_path):
        print("模型已存在，跳過下載。")
    else:
        parts = ["model_part_aa", "model_part_ab", "model_part_ac", "model_part_ad", "model_part_ae"]

        downloaded_files = []
        for part in parts:
            file_path = download_file_with_retry(repo_id, part, model_dir)
            if file_path is None:
                with open("/app/download_failed", "w") as f:
                    f.write(f"fail: {part}\n")
                print(" 模型分割檔案下載失敗，中止程序。")
                return
            downloaded_files.append(file_path)

        # 合併分割檔案
        print("正在合併模型分割檔案...")
        try:
            with open(merged_model_path, "wb") as f_out:
                for file_path in downloaded_files:
                    with open(file_path, "rb") as f_in:
                        f_out.write(f_in.read())
            print(f"模型合併完成：{merged_model_path}")
        except Exception as e:
            print(f"合併檔案失敗：{e}")
            with open("/app/download_failed", "w") as f:
                f.write("fail: merge error\n")
            return

        # 刪除分割檔案
        for file_path in downloaded_files:
            try:
                os.remove(file_path)
                print(f"已刪除分割檔案 {file_path}")
            except Exception as e:
                print(f" 刪除 {file_path} 時發生錯誤：{e}")

    # 下載輔助檔案
    aux_files = ["config.json", "generation_config.json", "special_tokens_map.json",
                 "tokenizer.json", "tokenizer_config.json"]

    for file in aux_files:
        file_path = download_file_with_retry(repo_id, file, model_dir)
        if file_path is None:
            with open("/app/download_failed", "w") as f:
                f.write(f"fail: {file}\n")
            print("輔助檔案下載失敗，中止程序。")
            return

    # 所有檔案下載成功
    with open("/app/download_done", "w") as f:
        f.write("done")
    print(" 所有模型檔案與設定檔案下載成功！")

if __name__ == "__main__":
    download()
