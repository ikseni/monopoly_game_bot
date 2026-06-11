import os
from dotenv import load_dotenv

load_dotenv()

token_name = os.getenv("token_vk")
group_id = int(os.getenv("group_id_vk"))