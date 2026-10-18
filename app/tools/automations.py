"""
NOVA Automations & Intent Handler
----------------------------------
Handles direct desktop automations requested by voice or text:
- Web navigation & YouTube playback (e.g. "YouTube var [song] lav", "play [song] on YouTube")
- Google Search
- Opening applications (Chrome, Notepad, Calculator, VS Code, Explorer)
- Volume and system controls
- User identity & Memory shortcuts ("Maja nav Balaji ahe", "Me Balaji ahe")
"""

import os
import re
import urllib.parse
import webbrowser
import subprocess
import platform
from typing import Tuple, Optional

from app.core.logger import get_logger
from app.memory.store import MemoryStore

logger = get_logger(__name__)
_memory = MemoryStore()


def get_chrome_path() -> Optional[str]:
    """Find Google Chrome executable on Windows."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def open_url(url: str) -> bool:
    """Open URL in Chrome if available, otherwise in default browser."""
    chrome = get_chrome_path()
    if chrome and os.path.exists(chrome):
        try:
            subprocess.Popen([chrome, url])
            return True
        except Exception as e:
            logger.warning("Could not launch Chrome directly: %s, falling back to webbrowser", e)
    return webbrowser.open(url)


def is_marathi_context(text: str) -> bool:
    """Check if query is in Marathi (Devanagari or common Marathi words)."""
    if any('\u0900' <= ch <= '\u097f' for ch in text):
        return True
    lower = text.lower()
    marathi_markers = ["lav", "kar", "suru", "ahe", "me ", "mi ", "kasa", "kashi", "chalav", "shodha", "tula", "mala", "tujha", "maja", "kay", "kon"]
    return any(w in lower for w in marathi_markers)


def play_youtube(query: str, is_mr: bool = False) -> str:
    """
    Open YouTube and search/play the requested song or video.
    """
    clean_q = query.strip()
    if not clean_q:
        url = "https://www.youtube.com"
        open_url(url)
        return "यूट्यूब उघडले आहे." if is_mr else "YouTube is now open."

    encoded = urllib.parse.quote_plus(clean_q)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    open_url(url)
    if is_mr:
        return f"यूट्यूबवर '{clean_q}' सर्च केले आहे आणि गाणं लावले आहे."
    return f"Opened YouTube and playing {clean_q} for you!"


def search_google(query: str, is_mr: bool = False) -> str:
    """
    Perform a Google search in the browser.
    """
    encoded = urllib.parse.quote_plus(query.strip())
    url = f"https://www.google.com/search?q={encoded}"
    open_url(url)
    if is_mr:
        return f"गुगलवर '{query.strip()}' सर्च केले आहे."
    return f"Searched for '{query.strip()}' on Google."


def open_application(app_name: str, is_mr: bool = False) -> Tuple[bool, str]:
    """
    Open common Windows applications.
    """
    name = app_name.lower().strip()
    apps = {
        "chrome": get_chrome_path() or "start chrome",
        "google chrome": get_chrome_path() or "start chrome",
        "browser": "start",
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "explorer": "explorer.exe",
        "files": "explorer.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "code": "code.cmd",
        "vs code": "code.cmd",
        "vscode": "code.cmd",
        "task manager": "taskmgr.exe",
    }

    if name in apps:
        cmd = apps[name]
        try:
            if " " in cmd and not os.path.isabs(cmd):
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen([cmd], shell=False)
            if is_mr:
                return True, f"{name.capitalize()} उघडले आहे."
            return True, f"Opened {name.capitalize()} for you!"
        except Exception as e:
            if is_mr:
                return False, f"{name} उघडताना समस्या आली."
            return False, f"Could not open {name}: {e}"

    try:
        subprocess.Popen(["start", name], shell=True)
        if is_mr:
            return True, f"{name} सुरू करण्याचा प्रयत्न केला आहे."
        return True, f"Attempted to open {name}."
    except Exception as e:
        if is_mr:
            return False, "अ‍ॅप सापडले नाही."
        return False, f"Application not found: {e}"


def handle_system_command(cmd: str, is_mr: bool = False) -> Tuple[bool, str]:
    """
    Handle basic system commands like lock screen, volume.
    """
    c = cmd.lower().strip()
    if any(k in c for k in ["lock screen", "lock laptop", "laptop lock", "screen lock"]):
        try:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            if is_mr:
                return True, "लॅपटॉप लॉक केला आहे."
            return True, "Your laptop is now locked."
        except Exception as e:
            if is_mr:
                return False, "लॅपटॉप लॉक करता आला नाही."
            return False, f"Could not lock screen: {e}"

    return False, ""


def handle_intent(text: str) -> Tuple[bool, str]:
    """
    Analyze user text (Marathi / Hindi / English / Hinglish / Marathish)
    and execute matching tool/action if it's an action command.

    Returns:
        (is_action, response_message)
    """
    if not text:
        return False, ""

    raw = text.strip()
    lower = raw.lower()
    is_mr = is_marathi_context(raw)

    # 1. Who am I query (Must check BEFORE name introduction)
    if any(q in lower for q in ["who am i", "me kon ahe", "mi kon ahe", "maja nav kay ahe", "mera naam kya hai", "who i am"]):
        all_memories = _memory.list_all()
        found_name = "Balaji"
        for m in all_memories:
            c = m.get("content", "")
            if "name is" in c.lower() or "nav" in c.lower():
                if "name is kon" not in c.lower():
                    # extract just the name
                    parts = re.findall(r"name is ([a-zA-Z\u0900-\u097F]+)", c, re.IGNORECASE)
                    if parts:
                        found_name = parts[0]
                    break
        if is_mr:
            return True, f"तुम्ही सांगितल्याप्रमाणे तुमचे नाव {found_name} आहे."
        return True, f"According to my memory, your name is {found_name}!"

    # 2. Identity / Name Introduction
    name_match = re.search(
        r"(?:me|mi|my name is|maja nav|mera naam|i am|i'm)\s+([a-zA-Z\u0900-\u097F]+)(?:\s+ahe|\s+hai)?",
        lower,
    )
    if name_match and not any(w in lower for w in ["youtube", "google", "chrome", "search", "play"]):
        candidate = name_match.group(1).strip()
        if candidate.lower() not in ["kon", "kay", "kya", "who", "what", "ready", "fine", "ok"]:
            user_name = candidate.capitalize()
            _memory.save(f"User's name is {user_name}.", tags="profile,name")
            if is_mr:
                return True, f"नमस्कार {user_name}! मी तुमचे नाव लक्षात ठेवले आहे. बोला मी काय मदत करू?"
            return True, f"Hello {user_name}! I've saved your name. How can I help you today?"

    # 3. Capabilities / What can you do
    if any(q in lower for q in [
        "tu kay kay", "kay karu shakto", "tula kay karta yete", "what can you do", "help me",
        "kai kai", "kaya kaya", "tula kay yete", "what are your abilities"
    ]):
        if is_mr:
            return True, "बालाजी, मी यूट्यूबवर गाणी लावू शकते, गुगल सर्च करू शकते, क्रोम किंवा इतर अ‍ॅप्स उघडू शकते आणि सर्व प्रश्नांची उत्तरे देऊ शकते!"
        return True, "Balaji, I can play songs on YouTube, search Google, open Chrome and desktop apps, lock your screen, and answer any questions!"

    # 4. Greetings
    if any(q in lower for q in ["kasa ahes", "kasi ahes", "how are you", "kasa chalalay"]):
        if is_mr:
            return True, "मी एकदम छान आहे बालाजी! तुम्ही कसे आहात? बोला काय मदत करू?"
        return True, "I'm doing wonderful Balaji! How are you doing today? What can I help you with?"

    # 5. YouTube - Play song or search
    # 5. YouTube - Play song or search
    yt_patterns = [
        r"(?:youtube|you to|u tube)\s+(?:var|pe|par)\s*(.*?)\s*(?:lav|play kar|search kar|open kar|chalav|gunalaw)",
        r"(?:play|lav|chalav)\s+(.*?)\s+(?:on|var|pe)\s+(?:youtube|you to|u tube)",
        r"(?:play|search)\s+(.*?)\s+on\s+(?:youtube|you to|u tube)",
        r"play\s+(.*?)\s+(?:song|gaana|track|music)",
        r"(.*?)\s+(?:song|gaana|gaan|gani|गाणं|गाणी)\s*(?:lav|play kar|chalav|बजाओ)",
        r"(?:gaan|gaana|gani|गाणं|गाणी|song)\s+(?:lav|play|chalav)",
    ]
    for pat in yt_patterns:
        m = re.search(pat, lower)
        if m:
            query = m.group(1).strip() if m.groups() else ""
            query = re.sub(r"\b(song|gaana|gaan|gani|गाणं|गाणी|video|track|please|mala|var|pe|on|and|you|to|work)\b", "", query, flags=re.IGNORECASE).strip()
            if not query:
                query = "latest songs"
            msg = play_youtube(query, is_mr=is_mr)
            return True, msg

    # Phonetic fallback for common Whisper mishearing of "YouTube var gaan lav"
    if any(k in lower for k in ["gunalaw", "gaan lav", "gaana lav", "गाणं लाव"]) or (
        ("youtube" in lower or "you to" in lower) and any(k in lower for k in ["song", "music", "play", "lav", "chalav", "video", "gana"])
    ):
        clean_q = re.sub(r"\b(and|you|to|work|on|gunalaw|youtube|var|pe|song|gaana|gaan|lav|play|please)\b", "", lower).strip()
        query = clean_q if clean_q else "top trending songs"
        msg = play_youtube(query, is_mr=is_mr)
        return True, msg

    if ("youtube" in lower or "you to" in lower) and any(w in lower for w in ["open", "chalav", "suru", "ja"]):
        open_url("https://www.youtube.com")
        return True, "यूट्यूब उघडले आहे." if is_mr else "YouTube is now open."

    # 6. Google Search
    google_patterns = [
        r"google\s+(?:var|pe|par)\s+(.*?)\s+(?:search|shodha|pah|bagh)",
        r"(?:search|shodha)\s+(.*?)\s+(?:on|var)\s+google",
    ]
    for pat in google_patterns:
        m = re.search(pat, lower)
        if m:
            query = m.group(1).strip()
            msg = search_google(query, is_mr=is_mr)
            return True, msg

    if "google" in lower and any(w in lower for w in ["open", "suru", "ja"]):
        open_url("https://www.google.com")
        return True, "गुगल उघडले आहे." if is_mr else "Google is now open."

    # 7. Chrome / Browser Launch
    if any(w in lower for w in ["chrome", "crome"]):
        if any(w in lower for w in ["open", "ja", "suru", "start"]):
            open_url("https://www.google.com")
            return True, "क्रोम ब्राउझर उघडले आहे." if is_mr else "Google Chrome is now open."

    # 8. Open specific app
    app_match = re.search(r"(?:open|suru kar|chalav)\s+([a-zA-Z0-9\s]+)", lower)
    if not app_match:
        app_match = re.search(r"([a-zA-Z0-9\s]+)\s+(?:open kar|suru kar|chalav)", lower)

    if app_match:
        candidate_app = app_match.group(1).strip()
        if candidate_app in ["notepad", "calculator", "calc", "explorer", "chrome", "vscode", "vs code", "terminal", "task manager"]:
            ok, msg = open_application(candidate_app, is_mr=is_mr)
            return ok, msg

    # 9. System commands (lock screen)
    sys_ok, sys_msg = handle_system_command(lower, is_mr=is_mr)
    if sys_ok:
        return True, sys_msg

    return False, ""

