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

FPS = 25
PRE_SECONDS = 30
POST_SECONDS = 5
BUFFER_SIZE = FPS * (PRE_SECONDS + POST_SECONDS)

SESSION_DATE = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join(os.getcwd(), "lances", SESSION_DATE)
os.makedirs(BASE_DIR, exist_ok=True)

# ==============================
# CÂMERAS
# ==============================

RTSP_URL_1 = "rtsp://admin:Networks124@192.168.0.15:1857/cam/realmonitor?channel=1&subtype=1"
RTSP_URL_2 = "rtsp://admin:Networks124@192.168.0.139:1857/cam/realmonitor?channel=1&subtype=1"


def conectar_camera(rtsp):
    print("Conectando câmera:", rtsp)
    cap = cv2.VideoCapture(rtsp, cv2.CAP_FFMPEG)
    time.sleep(2)

    if cap.isOpened():
        print("Câmera conectada")
        return cap
    else:
        print("Falha ao conectar câmera")
        return None


cap1 = conectar_camera(RTSP_URL_1)
cap2 = conectar_camera(RTSP_URL_2)

if cap1 is None or cap2 is None:
    print("Erro ao conectar nas câmeras")
    exit()

ret1, frame1 = cap1.read()

if not ret1:
    print("Erro ao capturar primeiro frame da câmera 1.")
    exit()

height, width, _ = frame1.shape

real_fps_cam1 = cap1.get(cv2.CAP_PROP_FPS) or 20
real_fps_cam2 = cap2.get(cv2.CAP_PROP_FPS) or 20

print(f"FPS cam1: {real_fps_cam1}")
print(f"FPS cam2: {real_fps_cam2}")

# ==============================
# CONTROLE DO BOTÃO
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
# BUFFERS
# ==============================

buffer1 = deque(maxlen=BUFFER_SIZE)
buffer2 = deque(maxlen=BUFFER_SIZE)

buffer1_lock = threading.Lock()
buffer2_lock = threading.Lock()

cooldown = False

# controle de congelamento
last_frame_cam1 = time.time()
last_frame_cam2 = time.time()

print("Sistema iniciado")
print("Pressione botão para salvar lance")

# ==============================
# FUNÇÃO SALVAR LANCE
# ==============================

def salvar_lance(buffer, lock, sufixo):

    print(f"Salvando lance {sufixo}")

    # Espera os 5 segundos após o clique
    print("Aguardando pós-evento...")
    time.sleep(POST_SECONDS)

    timestamp = datetime.now().strftime("%H-%M-%S-%f")

    video_name = f"lance_{timestamp}_{sufixo}.mp4"
    video_path = os.path.join(BASE_DIR, video_name)

    # Copia o buffer APÓS esperar os 5 segundos
    with lock:
        frames = list(buffer)[-BUFFER_SIZE:]

    if len(frames) == 0:
        print("Buffer vazio.")
        return

    fps = real_fps_cam1 if sufixo == "cam1" else real_fps_cam2

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    out = cv2.VideoWriter(
        video_path,
        fourcc,
        fps,
        (width, height)
    )

    if not out.isOpened():
        print("Erro abrindo VideoWriter.")
        return

    gravados = 0

    for frame in frames:

        if frame is None:
            continue

        try:
            out.write(frame)
            gravados += 1
        except Exception as e:
            print("Erro escrevendo frame:", e)

    out.release()
    del out

    time.sleep(1)

    if not os.path.exists(video_path):
        print("Vídeo não foi criado.")
        return

    tamanho = os.path.getsize(video_path)

    if tamanho < 50000:
        print("Vídeo inválido:", tamanho)
        return

    print(f"Frames gravados: {gravados}")
    print(f"Tamanho: {tamanho} bytes")

    # ======================
    # FASTSTART
    # ======================

    print("Aplicando faststart")

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

        if os.path.exists(temp_path):
            os.replace(temp_path, video_path)

    except Exception as e:
        print("Erro ffmpeg:", e)
        return

    # ======================
    # UPLOAD
    # ======================

    try:

        file_id = upload_para_r2(video_path)

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

        print("Lance registrado no banco")

    except Exception as e:
        print("Erro upload:", e)  


# ==============================
# LOOP PRINCIPAL
# ==============================

while True:

    ret1, frame1 = cap1.read()
    ret2, frame2 = cap2.read()

    # ------------------------------
    # CAMERA 1
    # ------------------------------

    if ret1:
        with buffer1_lock:
            buffer1.append(frame1)
        last_frame_cam1 = time.time()
        cv2.imshow("Camera 1", frame1)

    else:
        print("Falha camera 1, reconectando...")
        cap1.release()
        cap1 = conectar_camera(RTSP_URL_1)
        continue

    # detectar congelamento
    if time.time() - last_frame_cam1 > 3:
        print("Camera 1 congelou, reiniciando")
        cap1.release()
        cap1 = conectar_camera(RTSP_URL_1)

    # ------------------------------
    # CAMERA 2
    # ------------------------------

    if ret2:
        with buffer2_lock:
            buffer2.append(frame2)
        last_frame_cam2 = time.time()
        cv2.imshow("Camera 2", frame2)

    else:
        print("Falha camera 2, reconectando...")
        cap2.release()
        cap2 = conectar_camera(RTSP_URL_2)
        continue

    if time.time() - last_frame_cam2 > 3:
        print("Camera 2 congelou, reiniciando")
        cap2.release()
        cap2 = conectar_camera(RTSP_URL_2)

    # ------------------------------

    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break

    pygame.event.pump()

    if joystick.get_button(0):

        if not cooldown:

            cooldown = True

            # salva em thread para não travar sistema
            threading.Thread(
                target=salvar_lance,
                args=(buffer1, buffer1_lock, "cam1")
            ).start()
            
            threading.Thread(
                target=salvar_lance,
                args=(buffer2, buffer2_lock, "cam2")
            ).start()

            time.sleep(1)

            cooldown = False

cap1.release()
cap2.release()
cv2.destroyAllWindows()