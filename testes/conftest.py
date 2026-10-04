import os

# Chave usada pela sessão web e pelo JWT durante os testes
os.environ.setdefault("JWT_SECRET_KEY", "chave-de-teste-com-pelo-menos-32-bytes")
