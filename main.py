from fastapi import FastAPI
from transformers import AutoModelForCausalLM, AutoTokenizer
import aio_pika
import asyncio
import json
import re
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import torch

class MessageModel(BaseModel):
    prompt: str
    userId: str
    sender: str

class Settings(BaseSettings):
    RABBITMQ_HOST: str = "localhost"

    class Config:
        env_prefix = ""
        case_sensitive = False  # 允許大小寫不敏感
class MessageModel(BaseModel):
    prompt: str
    userId: str
    sender: str


app = FastAPI()
settings = Settings()
@app.get('/hi')
async def test():
    return 123
# 模型加載
model_path = "./model"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(model_path, device_map="auto")

# # RabbitMQ 連接資訊
RABBITMQ_URL = f"amqp://guest:guest@{settings.RABBITMQ_HOST}/"
EXCHANGE_NAME = "chatExchange"  # 與 Java 代碼一致
ROUTING_KEY = "private"  # 與 Java 代碼一致


@app.post('/generate')
async def send_to_rabbitmq(data: MessageModel):
    """將 LLM 生成的結果發送到 RabbitMQ，並設置 exchange 和 routing_key"""
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()

        # 確保交換機已宣告 (類型與 Java 一致)
        exchange = await channel.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
        input_text = f"<s>[INST] {data.prompt} [/INST]"
        # 創建消息，並附帶 headers
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(device)
        inputs = tokenizer(input_text, return_tensors="pt").to(device)
      
        outputs = model.generate(
            **inputs,
            max_length=150,  # 限制總長度
            max_new_tokens=50,  # 限制模型新增的 token 數量
            repetition_penalty=1.2,  # 減少重複回應
            temperature=0.7,  # 控制隨機性
            top_p=0.9,  # 過濾低機率詞
            do_sample=True  # 啟用隨機採樣
        )
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        pattern = r"\[/INST\](.*?)</s>"

        match = re.search(pattern, response)
        if match:
            extracted_text = match.group(1).strip()  # 提取匹配的內容並去除前後空白
            print("提取的文字:", extracted_text)
        else:
            print("沒有找到匹配的文字")
        message_data = {
            "userId": data.userId,
            "message": extracted_text
        }
       
        # 轉換成 JSON
        message_body = json.dumps(message_data)
        message_obj = aio_pika.Message(
            body=message_body.encode(),
            headers={"userId": data.sender}
        )
        # 發送消息到指定的 exchange 和 routing key
        await exchange.publish(message_obj, routing_key=ROUTING_KEY)

        return {'response':'ok'}
