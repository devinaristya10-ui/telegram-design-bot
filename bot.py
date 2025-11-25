import os
import telebot
from telebot import types
import requests
import urllib3
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import queue
import logging
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

urllib3.disable_warnings()

BOT_TOKEN = os.environ.get('BOT_TOKEN', '8256196995:AAGSnA8u62kldlQf3ueQCUIs3f-t7yIDytE')
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=10)

FIREBASE_KEYS = [
    "AIzaSyAJGrgbFGB_-h8V2oJLr4b-_ipetqM0duU",
    "AIzaSyDCWOmQ96XqXrL5rr1Xx8x5x5x5x5x5x5x5",
    "AIzaSyBv7Xq5x5x5x5x5x5x5x5x5x5x5x5x5x5x5x5",
]

STYLES = [
    ("diversity", "التنوع", "Diversity"),
    ("hyper-realistic", "واقعي متقدم", "Hyper-Realistic"),
    ("impressionist", "انطباعي", "Impressionist"),
    ("low-poly", "بولي منخفض", "Low-Poly"),
    ("isometric", "أيزومتريك", "Isometric"),
    ("cyberpunk", "سايبربنك", "Cyberpunk"),
    ("baroque", "باروك", "Baroque"),
    ("abstract-expressionism", "تعبيري مجرد", "Abstract Expressionism"),
    ("photorealistic-cgi", "CGI واقعي", "Photorealistic CGI"),
    ("surrealist", "سريالي", "Surrealist")
]

SIZES = [
    ("SQUARE_HD", "مربع ١:١", "Square 1:1"),
    ("PORTRAIT_4_3", "طولي ٣:٤", "Portrait 3:4"),
    ("PORTRAIT_16_9", "طولي ٩:١٦", "Portrait 9:16"),
    ("LANDSCAPE_4_3", "عرضي ٤:٣", "Landscape 4:3"),
    ("LANDSCAPE_16_9", "عرضي ١٦:٩", "Landscape 16:9")
]

user_state = {}
user_data = {}
user_language = {}

TEXTS = {
    'ar': {
        'welcome': "اختر اللغة:",
        'generate_images': "توليد صور جديدة",
        'choose_style': "اختر النمط:",
        'choose_size': "اختر القياس:",
        'write_prompt': "اكتب وصف الصورة:",
        'generating': "جاري توليد 6 صور...",
        'regenerating': "جاري توليد 4 صور إضافية...",
        'finished': "تم الانتهاء من إرسال الصور",
        'regenerate': "إعادة التوليد (4 صور)",
        'new_images': "صور جديدة (6 صور)",
        'start': "البداية",
        'back_styles': "الرجوع للأنماط",
        'back_sizes': "الرجوع للقياسات",
        'no_images': "لم يتم توليد الصور",
        'error': "حدث خطأ",
        'no_previous': "لا توجد إعدادات سابقة",
        'rate_limit': "الخادم مشغول حالياً، يرجى المحاولة بعد قليل"
    },
    'en': {
        'welcome': "Choose language:",
        'generate_images': "Generate New Images",
        'choose_style': "Choose style:",
        'choose_size': "Choose size:",
        'write_prompt': "Write image description:",
        'generating': "Generating 6 images...",
        'regenerating': "Generating 4 additional images...",
        'finished': "Finished sending images",
        'regenerate': "Regenerate (4 images)",
        'new_images': "New Images (6 images)",
        'start': "Start",
        'back_styles': "Back to Styles",
        'back_sizes': "Back to Sizes",
        'no_images': "No images generated",
        'error': "Error occurred",
        'no_previous': "No previous settings",
        'rate_limit': "Server is busy, please try again later"
    }
}

class EnhancedGenerationQueue:
    def __init__(self, max_concurrent=6, max_queue_size=500):
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.max_concurrent = max_concurrent
        self.current_tasks = 0
        self.semaphore = threading.Semaphore(max_concurrent)
        
    def add_task(self, task_data):
        try:
            if self.queue.qsize() < self.queue.maxsize:
                self.queue.put(task_data, timeout=1)
                return True
            return False
        except:
            return False
    
    def get_task(self):
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None
    
    def task_done(self):
        self.queue.task_done()

generation_queue = EnhancedGenerationQueue(max_concurrent=6, max_queue_size=500)

def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=50,
        pool_maxsize=50
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

http_session = create_session()

def get_text(user_id, text_key):
    lang = user_language.get(user_id, 'ar')
    return TEXTS[lang].get(text_key, text_key)

def get_token():
    headers = {
        'Content-Type': 'application/json',
        'X-Android-Package': 'com.photoroom.app',
        'X-Android-Cert': '0424A4898A4B33940D8BF16E44251B876E97F8D0',
        'Accept-Language': 'en-US',
        'X-Client-Version': 'Android/Fallback/X23002000/FirebaseCore-Android',
        'X-Firebase-GMPID': '1:456289768976:android:30c90b24b80bc2d1bfdc95',
        'X-Firebase-Client': 'H4sIAAAAAAAAAKtWykhNLCpJSk0sKVayio7VUSpLLSrOzM9TslIyUqoFAFyivEQfAAAA',
        'X-Firebase-AppCheck': 'eyJlcnJvciI6IlVOS05PV05fRVJST1IifQ==',
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 12)',
        'Host': 'www.googleapis.com',
    }

    for api_key in FIREBASE_KEYS:
        try:
            params = {'key': api_key}
            js = {
                'clientType': 'CLIENT_TYPE_ANDROID',
                'returnSecureToken': True
            }
            response = http_session.post(
                'https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser',
                headers=headers, 
                params=params, 
                json=js,
                timeout=10,
                verify=False
            )
            if response.status_code == 200:
                data = response.json()
                if "idToken" in data:
                    return data["idToken"]
        except:
            continue
    return None

def generate_images_optimized(prompt, styleId, sizeId, num_images=6):
    token = get_token()
    if not token:
        return [], []

    headers = {
        'Host': 'serverless-api.photoroom.com',
        'Accept': 'text/event-stream',
        'Authorization': token,
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'okhttp/4.12.0',
        'Pr-App-Version': '2025.47.03 (2180)',
        'Pr-Platform': 'android',
    }

    payload = {
        "userPrompt": prompt,
        "appId": "expert",
        "styleId": styleId,
        "sizeId": sizeId,
        "numberOfImages": num_images
    }

    try:
        resp = http_session.post(
            "https://serverless-api.photoroom.com/v2/ai-tools/generate-images",
            headers=headers,
            json=payload,
            stream=True,
            verify=False,
            timeout=60
        )

        bg = []
        nobg = []

        for line in resp.iter_lines():
            if not line:
                continue
            line_text = line.decode('utf-8', errors='ignore')
            if '"eventType":"aiImageResult"' in line_text:
                start_idx = line_text.find('"imageUrl":"') + 12
                end_idx = line_text.find('"', start_idx)
                if start_idx != -1 and end_idx != -1:
                    image_url = line_text[start_idx:end_idx].replace('\\', '')
                    bg.append(image_url)
            if '"eventType":"aiImageWithoutBackgroundResult"' in line_text:
                start_idx = line_text.find('"imageUrl":"') + 12
                end_idx = line_text.find('"', start_idx)
                if start_idx != -1 and end_idx != -1:
                    image_url = line_text[start_idx:end_idx].replace('\\', '')
                    nobg.append(image_url)

        return bg, nobg
        
    except:
        return [], []

def send_photos_fast(chat_id, urls):
    if not urls:
        return
        
    def send_photo(url):
        try:
            bot.send_photo(chat_id, url, timeout=20)
        except:
            pass
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(send_photo, urls)

def process_generation_queue():
    while True:
        try:
            if generation_queue.current_tasks < generation_queue.max_concurrent:
                task = generation_queue.get_task()
                if task:
                    with generation_queue.semaphore:
                        generation_queue.current_tasks += 1
                        threading.Thread(target=execute_generation_task, args=(task,), daemon=True).start()
            time.sleep(0.05)
        except:
            time.sleep(0.1)

def execute_generation_task(task_data):
    user_id, prompt, styleId, sizeId, num_images, message_id = task_data
    
    try:
        lang = user_language.get(user_id, 'ar')
        bg, nobg = generate_images_optimized(prompt, styleId, sizeId, num_images)
        
        if bg:
            send_photos_fast(user_id, bg)
            
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            kb.row(types.KeyboardButton(get_text(user_id, 'regenerate')))
            kb.row(types.KeyboardButton(get_text(user_id, 'new_images')))
            kb.row(types.KeyboardButton(get_text(user_id, 'start')))
            
            bot.send_message(
                user_id, 
                get_text(user_id, 'finished'),
                reply_markup=kb
            )
        else:
            bot.send_message(user_id, get_text(user_id, 'no_images'))
            
    except:
        try:
            bot.send_message(user_id, get_text(user_id, 'error'))
        except:
            pass
    finally:
        generation_queue.current_tasks -= 1
        try:
            bot.delete_message(user_id, message_id)
        except:
            pass

@bot.message_handler(commands=['start'])
def start(msg):
    user_id = msg.from_user.id
    
    try:
        gif_url = "https://media4.giphy.com/media/v1.Y2lkPTZjMDliOTUyb2NieXoyZDZyOWtibGI3ZWZicGo2MGIydG80emt0YjduMDEzcDUzZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/123t0dxx3bQdCE/giphy.gif"
        bot.send_animation(msg.chat.id, gif_url, caption="𝗗𝗘𝗦𝗜𝗚𝗡 𝗟𝗪𝗜𝗧")
    except:
        bot.send_message(msg.chat.id, "𝗗𝗘𝗦𝗜𝗚𝗡 𝗟𝗪𝗜𝗧")
    
    text = get_text(user_id, 'welcome')
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row(types.KeyboardButton("العربية"))
    kb.row(types.KeyboardButton("English"))
    
    bot.send_message(msg.chat.id, text, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in ["العربية", "English"])
def handle_language_selection(msg):
    user_id = msg.from_user.id
    
    if msg.text == "العربية":
        user_language[user_id] = 'ar'
    else:
        user_language[user_id] = 'en'
    
    show_main_menu(user_id)

def show_main_menu(user_id):
    text = get_text(user_id, 'choose_style')
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = []
    lang = user_language[user_id]
    for st_id, st_name_ar, st_name_en in STYLES:
        if lang == 'ar':
            buttons.append(types.KeyboardButton(st_name_ar))
        else:
            buttons.append(types.KeyboardButton(st_name_en))
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            kb.row(buttons[i], buttons[i + 1])
        else:
            kb.row(buttons[i])
    
    kb.row(types.KeyboardButton(get_text(user_id, 'start')))
    bot.send_message(user_id, text, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in [TEXTS['ar']['generate_images'], TEXTS['en']['generate_images']])
def handle_generate_new(msg):
    user_id = msg.from_user.id
    show_main_menu(user_id)

@bot.message_handler(func=lambda m: any(m.text in [st_name_ar, st_name_en] for _, st_name_ar, st_name_en in STYLES))
def handle_style_selection(msg):
    user_id = msg.from_user.id
    style_text = msg.text
    
    styleId = None
    for st_id, st_name_ar, st_name_en in STYLES:
        if style_text in [st_name_ar, st_name_en]:
            styleId = st_id
            break
    
    if not styleId:
        bot.send_message(user_id, get_text(user_id, 'error'))
        return
    
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["styleId"] = styleId

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    size_buttons = []
    lang = user_language[user_id]
    for sz_id, sz_name_ar, sz_name_en in SIZES:
        if lang == 'ar':
            size_buttons.append(types.KeyboardButton(sz_name_ar))
        else:
            size_buttons.append(types.KeyboardButton(sz_name_en))
    
    for i in range(0, len(size_buttons), 2):
        if i + 1 < len(size_buttons):
            kb.row(size_buttons[i], size_buttons[i + 1])
        else:
            kb.row(size_buttons[i])
    
    kb.row(types.KeyboardButton(get_text(user_id, 'back_styles')))
    kb.row(types.KeyboardButton(get_text(user_id, 'start')))
    bot.send_message(msg.chat.id, get_text(user_id, 'choose_size'), reply_markup=kb)

@bot.message_handler(func=lambda m: any(m.text in [sz_name_ar, sz_name_en] for _, sz_name_ar, sz_name_en in SIZES))
def handle_size_selection(msg):
    user_id = msg.from_user.id
    size_text = msg.text
    
    sizeId = None
    for sz_id, sz_name_ar, sz_name_en in SIZES:
        if size_text in [sz_name_ar, sz_name_en]:
            sizeId = sz_id
            break
    
    if not sizeId or user_id not in user_data or "styleId" not in user_data[user_id]:
        bot.send_message(user_id, get_text(user_id, 'error'))
        return
    
    user_data[user_id]["sizeId"] = sizeId
    user_state[user_id] = "await_prompt"

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton(get_text(user_id, 'back_sizes')))
    kb.row(types.KeyboardButton(get_text(user_id, 'start')))
    bot.send_message(msg.chat.id, get_text(user_id, 'write_prompt'), reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in [
    TEXTS['ar']['back_styles'], TEXTS['en']['back_styles'],
    TEXTS['ar']['back_sizes'], TEXTS['en']['back_sizes'], 
    TEXTS['ar']['start'], TEXTS['en']['start']
])
def handle_back_buttons(msg):
    user_id = msg.from_user.id
    
    if msg.text in [TEXTS['ar']['start'], TEXTS['en']['start']]:
        user_state.pop(user_id, None)
        user_data.pop(user_id, None)
        start(msg)
    
    elif msg.text in [TEXTS['ar']['back_styles'], TEXTS['en']['back_styles']]:
        user_state.pop(user_id, None)
        show_main_menu(user_id)
    
    elif msg.text in [TEXTS['ar']['back_sizes'], TEXTS['en']['back_sizes']]:
        if user_id in user_data:
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            size_buttons = []
            lang = user_language[user_id]
            for sz_id, sz_name_ar, sz_name_en in SIZES:
                if lang == 'ar':
                    size_buttons.append(types.KeyboardButton(sz_name_ar))
                else:
                    size_buttons.append(types.KeyboardButton(sz_name_en))
            
            for i in range(0, len(size_buttons), 2):
                if i + 1 < len(size_buttons):
                    kb.row(size_buttons[i], size_buttons[i + 1])
                else:
                    kb.row(size_buttons[i])
            
            kb.row(types.KeyboardButton(get_text(user_id, 'back_styles')))
            kb.row(types.KeyboardButton(get_text(user_id, 'start')))
            bot.send_message(msg.chat.id, get_text(user_id, 'choose_size'), reply_markup=kb)

@bot.message_handler(func=lambda m: user_state.get(m.from_user.id) == "await_prompt")
def handle_prompt(msg):
    user_id = msg.from_user.id
    prompt = msg.text

    if prompt in [
        TEXTS['ar']['back_styles'], TEXTS['en']['back_styles'],
        TEXTS['ar']['back_sizes'], TEXTS['en']['back_sizes'], 
        TEXTS['ar']['start'], TEXTS['en']['start']
    ]:
        return

    if user_id not in user_data:
        user_data[user_id] = {}
        
    user_data[user_id]["prompt"] = prompt
    styleId = user_data[user_id]["styleId"]
    sizeId = user_data[user_id]["sizeId"]

    user_state.pop(user_id, None)
    wait_msg = bot.send_message(user_id, get_text(user_id, 'generating'))
    
    task_data = (user_id, prompt, styleId, sizeId, 6, wait_msg.message_id)
    if not generation_queue.add_task(task_data):
        bot.send_message(user_id, get_text(user_id, 'rate_limit'))

@bot.message_handler(func=lambda m: m.text in [TEXTS['ar']['regenerate'], TEXTS['en']['regenerate']])
def handle_regenerate(msg):
    user_id = msg.from_user.id
    
    if user_id not in user_data or "prompt" not in user_data[user_id]:
        bot.send_message(user_id, get_text(user_id, 'no_previous'))
        start(msg)
        return

    prompt = user_data[user_id]["prompt"]
    styleId = user_data[user_id]["styleId"]
    sizeId = user_data[user_id]["sizeId"]

    wait_msg = bot.send_message(user_id, get_text(user_id, 'regenerating'))
    
    task_data = (user_id, prompt, styleId, sizeId, 4, wait_msg.message_id)
    if not generation_queue.add_task(task_data):
        bot.send_message(user_id, get_text(user_id, 'rate_limit'))

@bot.message_handler(func=lambda m: m.text in [TEXTS['ar']['new_images'], TEXTS['en']['new_images']])
def handle_new_images(msg):
    user_id = msg.from_user.id
    user_state.pop(user_id, None)
    show_main_menu(user_id)

if __name__ == "__main__":
    queue_thread = threading.Thread(target=process_generation_queue, daemon=True)
    queue_thread.start()
    
    logger.info("🚀 Starting Telegram Design Bot on Railway...")
    print("🤖 Bot is running on Railway...")
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"Bot error: {e}")
        print(f"❌ Bot stopped: {e}")