from fastapi import FastAPI
from transformers import AutoModelForCausalLM, AutoTokenizer
import aio_pika
import asyncio
import json
import re
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import torch
import os
from contextlib import asynccontextmanager

print("CUDA available:", torch.cuda.is_available())
print("GPU count:", torch.cuda.device_count())
print("GPU name:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A")

k = 1

class MessageModel(BaseModel):
    prompt: str
    userId: str
    sender: str

class Settings(BaseSettings):
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASS: str = "guest"

    class Config:
        env_prefix = ""  # 前綴
        case_sensitive = False # 大小寫不敏感

class MessageModel(BaseModel):
    prompt: str
    userId: str
    sender: str


app = FastAPI()
settings = Settings()

# 模型加載
model_path = "./model"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(model_path, device_map="auto")

login=os.getenv("RABBITMQ_USER", "guest"),
password=os.getenv("RABBITMQ_PASS", "guest"),

# # RabbitMQ 連接資訊

RABBITMQ_URL = f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASS}@{settings.RABBITMQ_HOST}/"
# RABBITMQ_URL = f"amqp://{login}:{password}@{settings.RABBITMQ_HOST}/"
EXCHANGE_NAME = "chatExchange"  # 與 Java 代碼一致
ROUTING_KEY = "private"  # 與 Java 代碼一致

# 模組級別初始化（FastAPI 啟動時只建立一次）
connection: aio_pika.RobustConnection = None
channel: aio_pika.Channel = None
exchange: aio_pika.Exchange = None




@asynccontextmanager
async def lifespan(app: FastAPI):
    global connection, channel, exchange

    # 建立連線
    connection = await aio_pika.connect_robust(
        RABBITMQ_URL,
        heartbeat=30
    )
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    print("RabbitMQ 連線已啟動")

    yield  # 👈 在這之後才會執行 FastAPI 的 endpoint

    # ⬇收尾關閉連線
    await connection.close()
    print("RabbitMQ 連線已關閉")

# 建立 FastAPI 實例，掛上 lifespan
app = FastAPI(lifespan=lifespan)


@app.get('/hi')
async def test():
    return 123
@app.post('/generate')
async def send_to_rabbitmq(data: MessageModel):
    print(f'收到{data.prompt}')
    input_text = f"<s>[INST] {data.prompt} [/INST]"
    async def run_generation(prompt: str):
 
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        def do_inference():
            inputs = tokenizer(prompt, return_tensors="pt").to(device)

            outputs = model.generate(
                **inputs,
                max_length=150,
                max_new_tokens=50,
                repetition_penalty=1.2,
                temperature=0.7,
                top_p=0.9,
                do_sample=True
            )
            return tokenizer.decode(outputs[0], skip_special_tokens=True)
      
        return await asyncio.to_thread(do_inference)
    try:
        # 將同步推論移至背景執行緒
        result = await run_generation(input_text)
        match = re.search(r"\[/INST\](.*?)</s>", result)
        extracted_text = match.group(1).strip() if match else "N/A"
        message_body = json.dumps({
            "userId": data.userId,
            "message": extracted_text
        })

        message_obj = aio_pika.Message(
            body=message_body.encode(),
            headers={"userId": data.sender}
        )
        # 發送結果給 RabbitMQ
        await exchange.publish(message_obj, routing_key=ROUTING_KEY)
        # message = aio_pika.Message(body=result.encode())
        # await exchange.publish(message, routing_key="room.0.answer")

        return {'response': 'ok'}

    except Exception as e:
        print(f"發送 RabbitMQ 時發生錯誤: {e}")
        return {"error": str(e)}
        #     match = re.search(r"\[/INST\](.*?)</s>", response)
        #     extracted_text = match.group(1).strip() if match else "N/A"

        #     message_body = json.dumps({
        #         "userId": data.userId,
        #         "message": extracted_text
        #     })

        #     message_obj = aio_pika.Message(
        #         body=message_body.encode(),
        #         headers={"userId": data.sender}
        #     )

        # await exchange.publish(message_obj, routing_key=ROUTING_KEY)

        # return {'response': 'ok'}

    # except aio_pika.exceptions.AMQPConnectionError as e:
    #     print("RabbitMQ 連線中斷:", e)
    #     return {"error": "connection_reset", "detail": str(e)}
    # except Exception as e:
    #     print("發送時發生錯誤:", e)
    #     return {"error": "unexpected", "detail": str(e)}

# @app.post('/generate')
# async def send_to_rabbitmq(data: MessageModel):
#     print(f'收到{data.prompt}')
#     """將 LLM 生成的結果發送到 RabbitMQ，並設置 exchange 和 routing_key"""
#     connection = await aio_pika.connect_robust(RABBITMQ_URL)
#     async with connection:
#         channel = await connection.channel()

#         # 確保交換機已宣告 (類型與 Java 一致)
#         exchange = await channel.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
#         input_text = f"<s>[INST] {data.prompt} [/INST]"
#         # 創建消息，並附帶 headers
#         device = "cuda" if torch.cuda.is_available() else "cpu"
#         print(device)
#         inputs = tokenizer(input_text, return_tensors="pt").to(device)
      
#         outputs = model.generate(
#             **inputs,
#             max_length=150,  # 限制總長度
#             max_new_tokens=50,  # 限制模型新增的 token 數量
#             repetition_penalty=1.2,  # 減少重複回應
#             temperature=0.7,  # 控制隨機性
#             top_p=0.9,  # 過濾低機率詞
#             do_sample=True  # 啟用隨機採樣
#         )
#         response = tokenizer.decode(outputs[0], skip_special_tokens=True)
#         pattern = r"\[/INST\](.*?)</s>"

#         match = re.search(pattern, response)
#         if match:
#             extracted_text = match.group(1).strip()  # 提取匹配的內容並去除前後空白
#             print("提取的文字:", extracted_text)
#         else:
#             print("沒有找到匹配的文字")
#         message_data = {
#             "userId": data.userId,
#             "message": extracted_text
#         }
       
#         # 轉換成 JSON
#         message_body = json.dumps(message_data)
#         message_obj = aio_pika.Message(
#             body=message_body.encode(),
#             headers={"userId": data.sender}
#         )
#         # 發送消息到指定的 exchange 和 routing key
#         await exchange.publish(message_obj, routing_key=ROUTING_KEY)

#         return {'response':'ok'}