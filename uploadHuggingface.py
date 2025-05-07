from huggingface_hub import HfApi
import os

# Hugging Face 帳號名稱與模型倉庫名稱
repo_id = "Bard504/llama3_ptt_1b"  

# 本地模型資料夾路徑
local_folder = "./upload" 

# 初始化 Hugging Face API
api = HfApi()

# 要上傳的所有檔案清單
files_to_upload = [
    "config.json",
    "generation_config.json",
    "model_part_aa",
    "model_part_ab",
    "model_part_ac",
    "model_part_ad",
    "model_part_ae",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json"
]

# 逐一上傳檔案到 Hugging Face 倉庫
for file in files_to_upload:
    file_path = os.path.join(local_folder, file)  # 合併成完整本地路徑
    print(f"正在上傳 {file_path} ...")

    api.upload_file(
        path_or_fileobj=file_path,  # 本地檔案路徑
        path_in_repo=file,          # 上傳到 Hugging Face 倉庫中的路徑
        repo_id=repo_id,            # Hugging Face 倉庫 ID
        repo_type="model"           # 指定倉庫類型為 "model"
    )

print("所有檔案上傳完成！")
