import logging
import os
from pathlib import Path

def setup_log(name: str) -> logging.Logger:
    """
    Configura el sistema de logging centralizado para todo el proyecto.
    Guarda los registros tanto en la consola como en un archivo .log.
    """
    # Identificamos la raíz del proyecto (subiendo un nivel desde 'utils')
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = Path(root_dir) / "logs"
    
    # Creamos la carpeta logs si por alguna razón no existe
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_path = log_dir / "scraper_bancos.log"
    
    # Crear logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Evitar que los mensajes se dupliquen si la función se llama varias veces
    if logger.handlers:
        return logger
        
    # Formato del mensaje (Fecha | Nivel | Archivo | Mensaje)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Handler para guardar en el archivo de texto
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Handler para mostrar en la terminal de VS Code
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger