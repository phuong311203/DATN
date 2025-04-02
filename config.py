import os

class Config:
    SECRET_KEY = os.urandom(24)
    MONGO_URI = "mongodb+srv://anhphuongphanqw:hgsBGUo5iBhsGJHT@cluster0.t4qnspy.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # URI kết nối MongoDB
