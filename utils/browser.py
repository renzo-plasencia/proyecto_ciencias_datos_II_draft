import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


import os
import subprocess
import time
import socket
import platform


def _get_chrome_path():
    """Detecta la ruta de Chrome según el SO."""
    system = platform.system()
    if system == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    elif system == "Linux":
        candidates = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser"]
    else:  # Mac
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]

    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("No se encontró Chrome. Ajusta la ruta manualmente.")


def _port_is_open(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def launch_debug_chrome(port=9222, profile_dir=None, chrome_path=None, log=None):
    """Lanza Chrome con remote-debugging-port si no está ya corriendo.
    Devuelve el objeto Popen si lo lanzó, o None si ya había uno corriendo."""
    if _port_is_open(port):
        if log:
            log.info(f"Chrome ya está corriendo en el puerto {port}, reutilizando.")
        return None

    chrome_path = chrome_path or _get_chrome_path()
    profile_dir = profile_dir or os.path.join(os.path.expanduser("~"), "ChromeProfileScraper")
    os.makedirs(profile_dir, exist_ok=True)

    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
    ]

    creationflags = subprocess.DETACHED_PROCESS if platform.system() == "Windows" else 0
    process = subprocess.Popen(cmd, creationflags=creationflags)

    for _ in range(20):
        if _port_is_open(port):
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("Chrome no abrió el puerto de debugging a tiempo.")

    if log:
        log.info(f"Chrome lanzado con debugging en puerto {port}, PID={process.pid}, perfil en {profile_dir}")
    return process  # <- ahora te quedas con el proceso para poder cerrarlo después


def close_debug_chrome(process, log=None):
    """Cierra específicamente el Chrome que lanzamos (y sus procesos hijos)."""
    if process is None:
        if log:
            log.info("No hay proceso de Chrome propio para cerrar (se reutilizó uno existente).")
        return

    system = platform.system()
    try:
        if system == "Windows":
            # /T mata todo el árbol de procesos hijos, /F fuerza el cierre
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=True,
                capture_output=True,
            )
        else:
            process.terminate()
            process.wait(timeout=5)
        if log:
            log.info(f"Chrome (PID={process.pid}) cerrado correctamente.")
    except Exception as e:
        if log:
            log.warning(f"No se pudo cerrar Chrome PID={process.pid}: {e}")


def setup_driver(headless=False, user_agents=None):
    """Conecta Selenium a un navegador Chrome real ya abierto por el usuario."""
    try:
        launch_debug_chrome(port=9222)
        opts = ChromeOptions()
        # Le decimos que se conecte al puerto del Chrome que abriste
        opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        
        driver = webdriver.Chrome(options=opts)
        driver.implicitly_wait(5)
        return driver
    except Exception as e:
        raise Exception(f"❌ ERROR: No se pudo conectar a Chrome. Asegúrate de haber ejecutado el comando de Windows+R antes de iniciar el script. Detalles: {e}")


# DEFAULT_USER_AGENTS = [
#     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
#     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
# ]

# def setup_driver(headless=True, user_agents=None):
#     opts = ChromeOptions()
#     user_agents = user_agents or DEFAULT_USER_AGENTS

#     # Opciones esenciales
#     if headless:
#         opts.add_argument("--headless=new")       # nuevo modo headless (Chrome 112+)
#     opts.add_argument("--no-sandbox")             # requerido en Linux/Docker
#     opts.add_argument("--disable-dev-shm-usage")  # evita crashes por poca memoria
#     opts.add_argument("--disable-gpu")

#     # Anti-deteccion de bot
#     opts.add_argument("--disable-blink-features=AutomationControlled")
#     opts.add_experimental_option("excludeSwitches", ["enable-automation"])
#     opts.add_experimental_option("useAutomationExtension", False)

#     # User-Agent realista
#     ua = random.choice(user_agents)
#     opts.add_argument(f"user-agent={ua}")

#     # Silenciar logs innecesarios
#     opts.add_argument("--log-level=3")

#     # ChromeDriver automatico
#     service = Service(ChromeDriverManager().install())
#     driver = webdriver.Chrome(service=service, options=opts)

#     # Timeout implicito global: espera hasta N seg antes de NoSuchElement
#     driver.implicitly_wait(5)
#     return driver

def scroll_suave(driver, paso=600, pausa=0.5):
    alto_pag = driver.execute_script('return document.body.scrollHeight')
    posicion_actual = 0
    while posicion_actual < alto_pag:
        posicion_actual += paso
        driver.execute_script(f'window.scrollTo(0, {posicion_actual});')
        time.sleep(pausa)
        alto_pag = driver.execute_script('return document.body.scrollHeight')