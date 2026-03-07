import os
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
import cv2
import time
from collections import deque
import threading
import pygame
from upload_r2 import upload_para_r2

# ==============================
# CONFIGURAÇÕES
# ==============================

FPS = 20
PRE_SECONDS = 20
POST_SECONDS = 3
BUFFER_SIZE = FPS * PRE_SECONDS

SESSION_DATE = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join(os.getcwd(), "lances", SESSION_DATE)
os.makedirs(BASE_DIR, exist_ok=True)

# ==============================
# CÂMERAS (DUAS PARA ORATORIO2)
# ==============================

RTSP_URL_1 = "rtsp://admin:Networks124@192.168.82.4:1857/cam/realmonitor?channel=1&subtype=0"
RTSP_URL_2 = "rtsp://admin:Networks124@192.168.82.152:1857/cam/realmonitor?channel=1&subtype=0"

cap1 = cv2.VideoCapture(RTSP_URL_1, cv2.CAP_FFMPEG)
cap2 = cv2.VideoCapture(RTSP_URL_2, cv2.CAP_FFMPEG)

time.sleep(2)

ret1, frame1 = cap1.read()
ret2, frame2 = cap2.read()

if not ret1 or not ret2:
    print("Erro ao conectar em uma das câmeras")
    exit()

height, width, _ = frame1.shape

# ==============================
# CONTROLE DO BOTÃO (ENCODER)
# ==============================

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("Nenhum encoder detectado")
    exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()
print("Encoder pronto:", joystick.get_name())

# ==============================
# BUFFERS DAS DUAS CÂMERAS
# ==============================

buffer1 = deque(maxlen=BUFFER_SIZE)
buffer2 = deque(maxlen=BUFFER_SIZE)

cooldown = False

print("Sistema iniciado")
print("Pressione o botão para salvar o lance")
print("Pressione Q para sair")

# ==============================
# FUNÇÃO PARA SALVAR LANCE
# ==============================

def salvar_lance(buffer, sufixo):
    print(f"Salvando lance {sufixo}...")

    timestamp = datetime.now().strftime("%H-%M-%S")
    video_name = f"lance_{timestamp}_{sufixo}.mp4"
    video_path = os.path.join(BASE_DIR, video_name)

    frames = list(buffer)

    if not frames:
        print("Buffer vazio")
        return

    # ==============================
    # 1️⃣ GERAÇÃO DO VÍDEO (OpenCV)
    # ==============================

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, FPS, (width, height))

    for frame in frames:
        overlay = frame.copy()

        texto = ""
        font = cv2.FONT_HERSHEY_SIMPLEX
        escala = 3.0
        espessura = 6

        (text_width, text_height), _ = cv2.getTextSize(texto, font, escala, espessura)

        pos_x = (width - text_width) // 2
        pos_y = (height + text_height) // 2

        cv2.putText(
            overlay,
            texto,
            (pos_x, pos_y),
            font,
            escala,
            (0, 255, 0),
            espessura
        )

        frame = cv2.addWeighted(overlay, 0.25, frame, 0.75, 0)
        out.write(frame)

    out.release()

    # ==============================
    # 2️⃣ OTIMIZAÇÃO PARA STREAMING
    # ==============================

    print("Aplicando faststart para streaming...")

    temp_path = video_path.replace(".mp4", "_fast.mp4")

    try:
        import subprocess

        subprocess.run([
            r"C:\ffmpeg\bin\ffmpeg.exe",
            "-y",
            "-i", video_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-profile:v", "high",
            "-level", "4.1",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            temp_path
        ], check=True)

        os.replace(temp_path, video_path)
        print("Vídeo otimizado com sucesso.")

    except Exception as e:
        print("Erro ao aplicar faststart:", e)
        print("Continuando com vídeo original (pode não funcionar streaming).")

    # ==============================
    # 3️⃣ UPLOAD PARA R2
    # ==============================

    print("Upload para R2...")

    try:
        file_id = upload_para_r2(video_path)
        print("Upload concluído")

        from app import app, db, Lance

        data = SESSION_DATE
        hora = timestamp.replace("-", ":")

        with app.app_context():
            novo_lance = Lance(
                quadra="oratorio2",
                data=data,
                hora=hora,
                drive_id=file_id
            )
            db.session.add(novo_lance)
            db.session.commit()

        print(f"Lance {sufixo} registrado no banco")

    except Exception as e:
        print("Erro ao registrar lance:", e)

# ==============================
# LOOP PRINCIPAL
# ==============================

while True:

    ret1, frame1 = cap1.read()
    ret2, frame2 = cap2.read()

    if ret1:
        buffer1.append(frame1)
        cv2.imshow("Camera 1", frame1)

    if ret2:
        buffer2.append(frame2)
        cv2.imshow("Camera 2", frame2)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('q') or key == ord('Q'):
        print("Encerrando sistema")
        break

    pygame.event.pump()

    if joystick.get_button(0):
        if not cooldown:
            cooldown = True
    
            salvar_lance(buffer1, "cam1")
            salvar_lance(buffer2, "cam2")
    
            time.sleep(1)
            cooldown = False

cap1.release()
cap2.release()
cv2.destroyAllWindows()