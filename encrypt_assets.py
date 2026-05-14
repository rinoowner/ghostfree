import base64

def encrypt(text, key):
    res = bytearray()
    key_bytes = key.encode('utf-8')
    text_bytes = text.encode('utf-8')
    for i in range(len(text_bytes)):
        res.append(text_bytes[i] ^ key_bytes[i % len(key_bytes)])
    return base64.b64encode(res).decode('utf-8')

key = "ghost_secret_key"

# Login
with open('app/src/main/assets/login.html', 'r', encoding='utf-8') as f:
    content = f.read()
    with open('login_enc.txt', 'w', encoding='utf-8') as out:
        out.write(encrypt(content, key))

# Dashboard
with open('app/src/main/assets/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()
    with open('dashboard_enc.txt', 'w', encoding='utf-8') as out:
        out.write(encrypt(content, key))

print("Encryption done!")
