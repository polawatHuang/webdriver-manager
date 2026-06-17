"""App-wide constants for TOA Lucky Draw Collector."""
import re

APP_NAME = "TOA Lucky Draw Collector"
WINDOW_SIZE = "1200x800"

# Set False only for local debugging — production runs hidden per spec.
HEADLESS = True

# Facebook scroll/expand loop tuning (empirically tune against a real large post).
STALE_ROUNDS_LIMIT = 5
MAX_TOTAL_ROUNDS = 200
SCROLL_WAIT_MS = 800
NAVIGATION_TIMEOUT_MS = 30_000

EMPLOYEE_ID_PATTERN = re.compile(r"\b\d{8}\b")

EXPORT_FOLDER_NAME = "TOA Lucky Draw Exports"
CSV_FILENAME_PREFIX = "facebook_comments"
CSV_ENCODING = "utf-8-sig"

LOG_MAX_BYTES = 2_000_000
LOG_BACKUP_COUNT = 5

# Colors — Corporate Blue / glassmorphism palette.
COLOR_BG = "#0F172A"
COLOR_CARD = "#1E293B"
COLOR_CARD_BORDER = "#334155"
COLOR_PRIMARY_BLUE = "#3B82F6"
COLOR_PRIMARY_PURPLE = "#8B5CF6"
COLOR_TEXT_PRIMARY = "#F8FAFC"
COLOR_TEXT_SECONDARY = "#94A3B8"
COLOR_SUCCESS = "#22C55E"
COLOR_WARNING = "#F59E0B"
COLOR_ERROR = "#EF4444"
COLOR_INFO = "#3B82F6"

PROGRESS_STAGES = [
    (0, "กำลังเชื่อมต่อ Browser..."),
    (15, "กำลังค้นหาคอมเมนต์..."),
    (43, "กำลังโหลดความคิดเห็นทั้งหมด..."),
    (87, "กำลังดึงข้อมูลพนักงาน..."),
    (100, "กำลังสร้างไฟล์ CSV..."),
]

CHROME_NOT_RUNNING_MSG = "กรุณาเปิด Google Chrome และ Login Facebook ก่อนใช้งาน"
BROWSER_LAUNCH_FAILED_MSG = (
    "ไม่สามารถเปิด Chrome ได้ กรุณาตรวจสอบว่าติดตั้ง Google Chrome แล้ว "
    "และลองเปิด Chrome ใหม่ก่อนใช้งาน"
)
POST_NOT_FOUND_MSG = "ไม่พบหน้าต่าง Facebook Post / กรุณาเปิดโพสต์ที่ต้องการก่อน"
EXPORT_FAILED_MSG = "ไม่สามารถบันทึกไฟล์ได้ / กรุณาปิดไฟล์ CSV ที่เปิดอยู่"
PROFILE_COPY_FAILED_MSG = "ไม่สามารถเข้าถึงโปรไฟล์ Chrome ได้ กรุณาลองใหม่"
INVALID_URL_MSG = "กรุณาวาง URL โพสต์ Facebook ที่ถูกต้อง"
