# 🏦 ETL de Productos Financieros Peruanos

Este proyecto es un pipeline de datos (ETL) construido en Python que extrae, limpia y consolida información sobre Cuentas de Ahorro, Depósitos a Plazo Fijo y Tarjetas de Crédito de los principales bancos del Perú (BCP, BBVA, Interbank, Scotiabank y BanBif).

El objetivo final es alimentar un Dashboard interactivo que recomiende los mejores productos financieros según el perfil del usuario.

## 🏗️ Arquitectura de Datos
El proyecto sigue una arquitectura de medallón:
* **Bronze (Raw):** Código HTML y datos extraídos en bruto mediante Web Scraping (Selenium + BeautifulSoup).
* **Silver (Cleansed):** Datos estandarizados, validados estrictamente con `pandera` y almacenados en formato `.parquet` por banco y producto.
* **Gold (Consumption):** Tablas maestras consolidadas y enriquecidas con KPIs de negocio (Valor Neto, Millas generadas, etc.) listas para el Dashboard.

---

## 🚀 Guía de Instalación y Ejecución

Para ejecutar este proyecto en tu entorno local, sigue estos pasos rigurosamente.

### 1. Pre-requisitos
* Tener **Python 3.9+** instalado.
* Tener el navegador **Google Chrome** instalado.
* Clonar este repositorio en tu computadora.

### 2. Configuración del Entorno Virtual
Abre la terminal en la carpeta raíz del proyecto y crea el entorno virtual:

#### En Windows (PowerShell / CMD):
```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual (PowerShell)
.\venv\Scripts\Activate.ps1

# O si usas CMD:
# .\venv\Scripts\activate.bat
```

```bash
### Instalación de Dependencias
Abre tu terminal en la carpeta raíz del proyecto y ejecuta:
pip install -r requirements.txt
```

### 3. Ejecución del Orquestador
Si se desea ejecutar la ETL para obtener las capas gold finales se debe usar la terminal y ejecutar:

```bash
python main_etl.py
```

### 4. Correr Dashboard
Para iniciar la aplicación interactiva en Streamlit, ejecute el siguiente comando en la terminal:

```bash
streamlit run Dashboard.py
```

- **Gestión de Datos:** Si existen datos procesados en la carpeta `output/gold`, el dashboard se cargará de inmediato omitiendo la ejecución automática del pipeline.
- **Actualización Automática:** Los datos se refrescan de forma programada cada `30 minutos`.
- **Ejecución Manual:** Es posible forzar la actualización de los datos en cualquier momento utilizando el botón de recarga disponible en la interfaz.

> Nota: Debido a que el proceso completo de ETL (scraping y limpieza) toma aproximadamente **16 minutos**, se utiliza el caché de la capa Gold para garantizar un inicio rápido del dashboard.


### 5. Ejecución Individual (Opcional)
Si deseas probar o debuggear el script de un solo banco sin correr todo el pipeline (que toma ~16 minutos), puedes ejecutar su módulo directamente:

# 🏦 Cuentas de Ahorro
## BCP
```bash
python modulos/cuentas_ahorro/etl_bcp_ahorros.py
```

## BBVA
```bash
python modulos/cuentas_ahorro/etl_bbva_ahorros.py
```

## Interbank
```bash
python modulos/cuentas_ahorro/etl_interbank_ahorros.py
```

## Scotiabank
```bash
python modulos/cuentas_ahorro/etl_scotiabank_ahorros.py
```

## BanBif (Local HTML)
```bash
python modulos/cuentas_ahorro/etl_banbif_ahorros.py
```

# 📈 Depósitos a Plazo Fijo
## Consolidado de todos los bancos
```bash
python modulos/depositos_plazo/etl_plazo_fijo.py
```

# 💳 Tarjetas de Crédito
## BCP
```bash
python modulos/tarjetas_credito/etl_bcp.py
```

## BBVA
```bash
python modulos/tarjetas_credito/etl_bbva.py
```

## Interbank
```bash
python modulos/tarjetas_credito/etl_interbank.py
```

## Scotiabank
```bash
python modulos/tarjetas_credito/etl_scotiabank.py
```

## BanBif (Local HTML)
```bash
python modulos/tarjetas_credito/etl_banbif.py
```