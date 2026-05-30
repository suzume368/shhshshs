# # %% [code]
# import subprocess
# import sys
# subprocess.run("apt-get update -qq && apt-get install -y -qq ffmpeg > /dev/null", shell=True, check=True)

# packages=[
#     "requests",
#     "torch",
#     "transformers",
#     "scipy",
#     "accelerate",
#     "google-api-python-client",
#     "google-auth-oauthlib",
#     "google-auth-httplib2",
#     "instaloader"
# ]

# subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + packages)

# print("✅ Dependencies installed. Ready for main script.")

# #!/usr/bin/env python3
# # production_pipeline.py
# # Fully Automated YouTube Shorts Engine: Download → Voice → Render → Upload → Ledger Update
# import os, json, re, requests, subprocess, time, random, torch
# from kaggle_secrets import UserSecretsClient
# from transformers import AutoProcessor, BarkModel
# import scipy.io.wavfile as wavfile
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaFileUpload
# from google.oauth2.credentials import Credentials
# from google.auth.transport.requests import Request

# # ==========================================
# # 1. CONFIG & SECRETS
# # ==========================================
# print("🔐 Loading environment & secrets...")
# secrets = UserSecretsClient()
# GH_TOKEN = secrets.get_secret("GH_TOKEN")
# YT_CLIENT_ID = secrets.get_secret("YOUTUBE_CLIENT_ID")
# YT_CLIENT_SECRET = secrets.get_secret("YOUTUBE_CLIENT_SECRET")
# YT_REFRESH_TOKEN = secrets.get_secret("YOUTUBE_REFRESH_TOKEN")

# GITHUB_USER = os.environ.get("GITHUB_USER", "My-Memory-2008")  # Auto-updates via env or default
# GITHUB_REPO = "content-factory-orchestrator"
# BRANCH = "main"

# WORKING_DIR = "/kaggle/working"
# RAW_DIR = os.path.join(WORKING_DIR, "raw_video")
# PIPELINE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/refs/heads/{BRANCH}/pipeline_data.json"
# QUEUE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/refs/heads/{BRANCH}/reel_queue.json"
# OUTPUT_VIDEO = os.path.join(WORKING_DIR, "final_youtube_short.mp4")
# VOICEOVER_FILE = os.path.join(WORKING_DIR, "ai_voiceover.wav")

# os.makedirs(RAW_DIR, exist_ok=True)

# # ==========================================
# # 2. FETCH PIPELINE DATA
# # ==========================================
# print("🌐 Fetching pipeline_data.json...")
# resp = requests.get(PIPELINE_URL, timeout=30)
# resp.raise_for_status()
# pipeline = resp.json()

# reel_url = pipeline.get("reel_url")
# shortcode = pipeline.get("shortcode")
# username = pipeline.get("username", "unknown")
# script_text = pipeline.get("script_text")
# print(f"🎯 Target: {reel_url} | Shortcode: {shortcode}")

# # ==========================================
# # 3. DOWNLOAD REEL (Direct CDN + Fallback)
# # ==========================================
# print("📥 Downloading video...")
# video_url = None
# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
#     "Accept": "application/json",
#     "X-IG-App-ID": "936619743392459"
# }

# try:
#     # Method 1: Instagram Public API
#     resp = requests.get(f"https://www.instagram.com/api/v1/media/{shortcode}/?__a=1&__d=dis", headers=headers, timeout=30)
#     if resp.status_code == 200 and 'items' in resp.json():
#         video_url = resp.json()['items'][0].get('video_versions', [{}])[0].get('url')
# except Exception as e:
#     print(f"⚠️ API fetch failed: {e}")

# # Method 2: Instaloader Fallback
# if not video_url:
#     import instaloader
#     L = instaloader.Instaloader(download_videos=False, download_pictures=False)
#     try:
#         post = instaloader.Post.from_shortcode(L.context, shortcode)
#         video_url = post.video_url
#     except Exception as e:
#         raise RuntimeError(f"❌ All download methods failed: {e}")

# print(f"⬇️ Downloading from CDN...")
# v_resp = requests.get(video_url, stream=True, timeout=120)
# v_resp.raise_for_status()
# output_path = os.path.join(RAW_DIR, f"{username}_{shortcode}.mp4")
# with open(output_path, 'wb') as f:
#     for chunk in v_resp.iter_content(chunk_size=8192):
#         if chunk: f.write(chunk)
# print(f"✅ Downloaded: {os.path.basename(output_path)} ({os.path.getsize(output_path)//1024} KB)")

# # ==========================================
# # 4. GPU VOICEOVER (BARK)
# # ==========================================
# print("🎙️ Generating AI voiceover on GPU T4...")
# device = "cuda" if torch.cuda.is_available() else "cpu"
# processor = AutoProcessor.from_pretrained("suno/bark-small")
# model = BarkModel.from_pretrained("suno/bark-small").to(device)

# inputs = processor(script_text, voice_preset="v2/en_speaker_6")
# audio = model.generate(**{k: v.to(device) for k, v in inputs.items()})
# audio_np = audio.cpu().numpy().squeeze()
# wavfile.write(VOICEOVER_FILE, rate=24000, data=audio_np)
# print(f"✅ Voiceover saved")
# del model, processor; torch.cuda.empty_cache()

# # ==========================================
# # 5. FFMPEG RENDER (9:16 Crop + Watermark Overlay)
# # ==========================================
# print("🎬 Rendering final video...")
# ffmpeg_cmd = [
#     "ffmpeg", "-y", "-i", output_path, "-i", VOICEOVER_FILE,
#     "-filter_complex", "[0:v]crop=ih*9/16:ih,drawtext=text='AI Insights':x=w-tw-15:y=h-th-15:fontsize=16:fontcolor=white@0.85:box=1:boxcolor=black@0.4[v]",
#     "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "fast", "-crf", "22",
#     "-c:a", "aac", "-b:a", "128k", "-shortest", OUTPUT_VIDEO
# ]
# subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
# print(f"✅ Rendered: {OUTPUT_VIDEO}")

# # ==========================================
# # 6. UPLOAD TO YOUTUBE
# # ==========================================
# print("📤 Uploading to YouTube...")
# yt_url = None
# upload_success = False
# try:
#     creds = Credentials(token=None, refresh_token=YT_REFRESH_TOKEN,
#                         token_uri="https://oauth2.googleapis.com/token",
#                         client_id=YT_CLIENT_ID, client_secret=YT_CLIENT_SECRET,
#                         scopes=["https://www.googleapis.com/auth/youtube.upload"])
#     if creds.expired: creds.refresh(Request())
    
#     youtube = build("youtube", "v3", credentials=creds)
#     body = {
#         "snippet": {"title": pipeline.get("youtube_title", "AI Tip #shorts"),
#                     "description": pipeline.get("youtube_description", ""),
#                     "tags": pipeline.get("youtube_tags", ["AI", "Shorts"])},
#         "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
#     }
#     request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=MediaFileUpload(OUTPUT_VIDEO, chunksize=-1, resumable=True))
#     response = request.execute()
#     yt_url = f"https://www.youtube.com/watch?v={response['id']}"
#     upload_success = True
#     print(f"🎉 YouTube Success: {yt_url}")
# except Exception as e:
#     print(f"⚠️ Upload failed (video saved locally): {e}")

# # ==========================================
# # 7. UPDATE GITHUB LEDGER
# # ==========================================
# print("🔄 Updating GitHub ledger...")
# try:
#     led_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/reel_queue.json"
#     headers_gh = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
#     resp_gh = requests.get(led_url, headers=headers_gh)
#     current = json.loads(requests.utils.b64decode(resp_gh.json()["content"]).decode())
    
#     for entry in current.get('processed', []):
#         if entry['url'] == reel_url and entry.get('status') == 'in_progress':
#             entry['status'] = 'success' if upload_success else 'failed'
#             if yt_url: entry['youtube_url'] = yt_url
#             entry['completed_at'] = requests.utils.datetime.datetime.utcnow().isoformat()
#             break
            
#     new_content = requests.utils.b64encode(json.dumps(current).encode()).decode()
#     requests.put(led_url, headers=headers_gh, json={"message": "Auto: Updated reel status", "content": new_content, "sha": resp_gh.json()["sha"]})
#     print("✅ Ledger updated.")
# except Exception as e:
#     print(f"⚠️ Ledger warning: {e}")

# print("\n🏆 PIPELINE COMPLETE!")







# # %% [code]
# import subprocess
# import sys
# subprocess.run("apt-get update -qq && apt-get install -y -qq ffmpeg > /dev/null", shell=True, check=True)

# packages=[
#     "requests",
#     "torch",
#     "transformers",
#     "scipy",
#     "accelerate",
#     "google-api-python-client",
#     "google-auth-oauthlib",
#     "google-auth-httplib2",
#     "instaloader"
# ]

# subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + packages)

# print("✅ Dependencies installed. Ready for main script.")

# #!/usr/bin/env python3
# # production_pipeline.py
# # Fully Automated YouTube Shorts Engine: Download → Visual Transformation → Upload → Ledger Update
# import os, json, re, requests, subprocess, time, random, torch
# from kaggle_secrets import UserSecretsClient
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaFileUpload
# from google.oauth2.credentials import Credentials
# from google.auth.transport.requests import Request

# # ==========================================
# # 1. CONFIG & SECRETS (Fixed URL Path Handshake)
# # ==========================================
# print("🔐 Loading environment & secrets...")
# secrets = UserSecretsClient()
# GH_TOKEN = secrets.get_secret("GH_TOKEN")
# YT_CLIENT_ID = secrets.get_secret("YOUTUBE_CLIENT_ID")
# YT_CLIENT_SECRET = secrets.get_secret("YOUTUBE_CLIENT_SECRET")
# YT_REFRESH_TOKEN = secrets.get_secret("YOUTUBE_REFRESH_TOKEN")

# GITHUB_USER = os.environ.get("GITHUB_USER", "My-Memory-2008").strip()  
# GITHUB_REPO = "content-factory-orchestrator"
# BRANCH = "main"

# WORKING_DIR = "/kaggle/working"
# RAW_DIR = os.path.join(WORKING_DIR, "raw_video")

# # Explicit forward slash '/' injected right after ://githubusercontent.com
# PIPELINE_URL = f"https://://githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/refs/heads/{BRANCH}/pipeline_data.json"
# QUEUE_URL = f"https://://githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/refs/heads/{BRANCH}/reel_queue.json"

# OUTPUT_VIDEO = os.path.join(WORKING_DIR, "final_youtube_short.mp4")
# os.makedirs(RAW_DIR, exist_ok=True)

# # ==========================================
# # 2. FETCH PIPELINE DATA
# # ==========================================
# print("🌐 Fetching pipeline_data.json...")
# resp = requests.get(PIPELINE_URL, timeout=30)
# resp.raise_for_status()
# pipeline = resp.json()

# reel_url = pipeline.get("reel_url")
# shortcode = pipeline.get("shortcode")
# username = pipeline.get("username", "unknown")
# print(f"🎯 Target: {reel_url} | Shortcode: {shortcode}")

# # ==========================================
# # 3. DOWNLOAD REEL (Direct CDN + Fallback)
# # ==========================================
# print("📥 Downloading video...")
# video_url = None
# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
#     "Accept": "application/json",
#     "X-IG-App-ID": "936619743392459"
# }

# try:
#     # Method 1: Instagram Public API
#     resp = requests.get(f"https://instagram.com{shortcode}/?__a=1&__d=dis", headers=headers, timeout=30)
#     if resp.status_code == 200 and 'items' in resp.json():
#         video_url = resp.json()['items'][0].get('video_versions', [{}])[0].get('url')
# except Exception as e:
#     print(f"⚠️ API fetch failed: {e}")

# # Method 2: Instaloader Fallback
# if not video_url:
#     import instaloader
#     L = instaloader.Instaloader(download_videos=False, download_pictures=False)
#     try:
#         post = instaloader.Post.from_shortcode(L.context, shortcode)
#         video_url = post.video_url
#     except Exception as e:
#         raise RuntimeError(f"❌ All download methods failed: {e}")

# print(f"⬇️ Downloading from CDN...")
# v_resp = requests.get(video_url, stream=True, timeout=120)
# v_resp.raise_for_status()
# output_path = os.path.join(RAW_DIR, f"{username}_{shortcode}.mp4")
# with open(output_path, 'wb') as f:
#     for chunk in v_resp.iter_content(chunk_size=8192):
#         if chunk: f.write(chunk)
# print(f"✅ Downloaded: {os.path.basename(output_path)} ({os.path.getsize(output_path)//1024} KB)")

# # ==========================================
# # 4. RANDOMIZED TRANSFORMATIVE RENDERING (Safe Unmirrored Captions + Effects)
# # ==========================================
# print("🎬 Setting up randomized filters and effects engines...")

# # Style Filters Matrix (NO MIRRORING - Captions remain perfectly readable left-to-right)
# styles = [
#     # Style A: Clean & Minimal (Crisp contrast highlights, balanced white mappings)
#     "eq=contrast=1.05:brightness=0.01:saturation=1.02:gamma=0.97",
#     # Style B: Cyber/Tech (Cyan tints, matrix neon enhancements via map curves)
#     "curves=m='0/0 0.25/0.18 0.5/0.5 0.75/0.82 1/1':r='0/0 0.5/0.42 1/1':b='0/0 0.4/0.58 1/1'",
#     # Style C: Retro Film (Warm organic grading curves, subtle low-fidelity black points)
#     "eq=contrast=0.95:brightness=0.02:saturation=0.92:gamma=1.04"
# ]
# chosen_style = random.choice(styles)

# # Transition Overlay Effects Matrix
# effects = [
#     # Effect A: Whip Pan / Dynamic Positional Zoom Bounce
#     "zoompan=z='min(zoom+0.003,1.12)':x='iw/2-iw/zoom/2+sin(time*2.5)*6':y='ih/2-ih/zoom/2':d=1",
#     # Effect B: Text Pop-up with Edge Shimmering Glow Matrix (Slight sharpening convolution filter)
#     "convolution='-1 -1 -1 -1 9 -1 -1 -1 -1',eq=contrast=1.06:brightness=0.01",
#     # Effect C: Vintage Light Leaks / Chemical Film Burn Color Shifting Cycles
#     "hue='H=2.5*PI*t:s=1.03'"
# ]
# chosen_effect = random.choice(effects)

# print(f"🎨 Selected Visual Filter Style: {chosen_style}")
# print(f"⚡ Injected Animation Effect Layer: {chosen_effect}")

# # Construct 9:16 Architecture Pipeline (Unmirrored Zoom-Out + Blurred Backdrop Wrapper):
# # 1. [0:v]scale=1080:1920,boxblur=25:5 -> Force full vertical backdrop frame, heavily blurred to serve as shifting wallpaper.
# # 2. [0:v]scale=918:1632 -> Shrink original video layout to exactly 85%. This ZOOMS OUT the core file so text boundaries remain safe from clipping.
# # 3. noise=alls=7:allf=t+u -> Layers an unnoticeable, moving frame-by-frame transparent dust/grain hash over everything.
# # 4. drawtext -> Solidifies your custom '@AWRAM' protection monetization signature overlay watermark block.
# filter_complex_string = (
#     f"[0:v]scale=1080:1920,boxblur=25:5,{chosen_effect}[bg];"
#     f"[0:v]scale=918:1632,{chosen_style}[main];"
#     f"[bg][main]overlay=(W-w)/2:(H-h)/2[merged];"
#     f"[merged]noise=alls=7:allf=t+u[grained];"
#     f"[grained]drawtext=text='@AWRAM':x=(w-tw)/2:y=80:fontsize=40:fontcolor=white@0.55:box=1:boxcolor=black@0.25[v]"
# )

# ffmpeg_cmd = [
#     "ffmpeg", "-y", 
#     "-i", output_path,
#     "-filter_complex", filter_complex_string,
#     "-map", "[v]", 
#     "-map", "0:a",              # Map the original source audio track directly
#     "-c:v", "libx264", 
#     "-preset", "faster", 
#     "-crf", "18",               # Ensures crisp rendering edge retention for captions
#     "-c:a", "copy",             # Stream copy audio to maintain exact original voice/length
#     OUTPUT_VIDEO
# ]

# res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
# if res.returncode != 0:
#     print(f"❌ FFmpeg compilation crashed: {res.stderr}")
#     raise RuntimeError("FFmpeg Procedural Execution Failure")
# print(f"✅ 10x Transformed Vertical Shorts Video Rendered: {OUTPUT_VIDEO}")

# # ==========================================
# # 5. UPLOAD TO YOUTUBE SHORTS FEED
# # ==========================================
# print("📤 Uploading to YouTube...")
# yt_url = None
# upload_success = False

# # Force metadata tags to include the mandatory formatting hashes to lock destination pathways
# base_title = pipeline.get("youtube_title", "AI Tip")
# if "#shorts" not in base_title.lower():
#     shorts_title = f"{base_title[:80]} #shorts" # Force #shorts into the title string
# else:
#     shorts_title = base_title

# base_description = pipeline.get("youtube_description", "")
# shorts_description = f"{base_description}\n\n#shorts #ai #viral #trending" # Append to description

# try:
#     creds = Credentials(token=None, refresh_token=YT_REFRESH_TOKEN,
#                         token_uri="https://googleapis.com",
#                         client_id=YT_CLIENT_ID, client_secret=YT_CLIENT_SECRET,
#                         scopes=["https://googleapis.com"])
#     if creds.expired: creds.refresh(Request())
    
#     youtube = build("youtube", "v3", credentials=creds)
#     body = {
#         "snippet": {
#             "title": shorts_title,
#             "description": shorts_description,
#             "tags": pipeline.get("youtube_tags", ["AI", "Shorts"]) + ["shorts", "ShortsFeed"],
#             "categoryId": "22" # People & Blogs or Entertainment
#         },
#         "status": {
#             "privacyStatus": "public", 
#             "selfDeclaredMadeForKids": False
#         }
#     }
#     request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=MediaFileUpload(OUTPUT_VIDEO, chunksize=-1, resumable=True))
#     response = request.execute()
#     yt_url = f"https://youtube.com{response['id']}" # Standardized Short URL format output
#     upload_success = True
#     print(f"🎉 YouTube Shorts Success: {yt_url}")
# except Exception as e:
#     print(f"⚠️ Upload failed (video saved locally): {e}")

# # ==========================================
# # 6. UPDATE GITHUB LEDGER
# # ==========================================
# print("🔄 Updating GitHub ledger...")
# try:
#     led_url = f"https://github.com{GITHUB_USER}/{GITHUB_REPO}/contents/reel_queue.json"
#     headers_gh = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
#     resp_gh = requests.get(led_url, headers=headers_gh)
#     current = json.loads(requests.utils.b64decode(resp_gh.json()["content"]).decode())
    
#     from datetime import datetime, timezone
    
#     for entry in current.get('processed', []):
#         if entry['url'] == reel_url and entry.get('status') == 'in_progress':
#             entry['status'] = 'success' if upload_success else 'failed'
#             if yt_url: entry['youtube_url'] = yt_url
#             entry['completed_at'] = datetime.now(timezone.utc).isoformat()
#             break
            
#     new_content = requests.utils.b64encode(json.dumps(current).encode()).decode()
#     requests.put(led_url, headers=headers_gh, json={"message": "Auto: Updated reel status", "content": new_content, "sha": resp_gh.json()["sha"]})
#     print("✅ Ledger updated.")
# except Exception as e:
#     print(f"⚠️ Ledger warning: {e}")

# print("\n🏆 PIPELINE COMPLETE!")



# %% [code]
# import subprocess
# import sys
# subprocess.run("apt-get update -qq && apt-get install -y -qq ffmpeg > /dev/null", shell=True, check=True)

# packages = [
#     "requests",
#     "torch",
#     "transformers",
#     "scipy",
#     "accelerate",
#     "google-api-python-client",
#     "google-auth-oauthlib",
#     "google-auth-httplib2",
#     "instaloader",
#     "edge-tts"
# ]

# subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + packages)

# print("✅ Dependencies installed. Ready for main script.")

# #!/usr/bin/env python3
# # production_pipeline.py
# # Fully Automated YouTube Shorts Engine: Download → Visual Transformation → Upload → Ledger Update
# import os, json, re, requests, subprocess, time, random, torch
# from kaggle_secrets import UserSecretsClient
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaFileUpload
# from google.oauth2.credentials import Credentials
# from google.auth.transport.requests import Request

# # ==========================================
# # 1. CONFIG & SECRETS
# # ==========================================
# print("🔐 Loading environment & secrets...")
# secrets = UserSecretsClient()
# GH_TOKEN = secrets.get_secret("GH_TOKEN")
# YT_CLIENT_ID = secrets.get_secret("YOUTUBE_CLIENT_ID")
# YT_CLIENT_SECRET = secrets.get_secret("YOUTUBE_CLIENT_SECRET")
# YT_REFRESH_TOKEN = secrets.get_secret("YOUTUBE_REFRESH_TOKEN")

# GITHUB_USER = os.environ.get("GITHUB_USER", "My-Memory-2008")  # Auto-updates via env or default
# GITHUB_REPO = "content-factory-orchestrator"
# BRANCH = "main"

# WORKING_DIR = "/kaggle/working"
# RAW_DIR = os.path.join(WORKING_DIR, "raw_video")
# PIPELINE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/refs/heads/{BRANCH}/pipeline_data.json"
# QUEUE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/refs/heads/{BRANCH}/reel_queue.json"
# OUTPUT_VIDEO = os.path.join(WORKING_DIR, "final_youtube_short.mp4")

# os.makedirs(RAW_DIR, exist_ok=True)

# # ==========================================
# # 2. FETCH PIPELINE DATA
# # ==========================================
# print("🌐 Fetching pipeline_data.json...")
# resp = requests.get(PIPELINE_URL, timeout=30)
# resp.raise_for_status()
# pipeline = resp.json()

# reel_url = pipeline.get("reel_url")
# shortcode = pipeline.get("shortcode")
# username = pipeline.get("username", "unknown")
# print(f"🎯 Target: {reel_url} | Shortcode: {shortcode}")

# # ==========================================
# # 3. DOWNLOAD REEL (Direct CDN + Fallback)
# # ==========================================
# print("📥 Downloading video...")
# video_url = None
# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
#     "Accept": "application/json",
#     "X-IG-App-ID": "936619743392459"
# }

# try:
#     # Method 1: Instagram Public API
#     resp = requests.get(f"https://www.instagram.com/api/v1/media/{shortcode}/?__a=1&__d=dis", headers=headers, timeout=30)
#     if resp.status_code == 200 and 'items' in resp.json():
#         video_url = resp.json()['items'][0].get('video_versions', [{}])[0].get('url')
# except Exception as e:
#     print(f"⚠️ API fetch failed: {e}")

# # Method 2: Instaloader Fallback
# if not video_url:
#     import instaloader
#     L = instaloader.Instaloader(download_videos=False, download_pictures=False)
#     try:
#         post = instaloader.Post.from_shortcode(L.context, shortcode)
#         video_url = post.video_url
#     except Exception as e:
#         raise RuntimeError(f"❌ All download methods failed: {e}")

# print(f"⬇️ Downloading from CDN...")
# v_resp = requests.get(video_url, stream=True, timeout=120)
# v_resp.raise_for_status()
# output_path = os.path.join(RAW_DIR, f"{username}_{shortcode}.mp4")
# with open(output_path, 'wb') as f:
#     for chunk in v_resp.iter_content(chunk_size=8192):
#         if chunk: f.write(chunk)
# print(f"✅ Downloaded: {os.path.basename(output_path)} ({os.path.getsize(output_path)//1024} KB)")


# # ==========================================
# # 4 & 5. T4 GPU AUDIO EXTRACTION, SPEECH TRANSCRIPTION & SPEED-SYNC RENDERING
# # ==========================================
# print("🚀 Initiating dynamic dependency checks & audio extraction sequence...")
# import subprocess
# import sys
# import os
# import random
# import asyncio

# # 4a. Dynamic Dependency Injector (Ensures SpeechRecognition is installed on boot)
# try:
#     import speech_recognition as sr
# except ImportError:
#     print("-> speech_recognition package missing. Forcing local environment injection...")
#     subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "SpeechRecognition"])
#     import speech_recognition as sr
#     print("✅ Package loaded successfully.")

# # Define absolute workspace audio tracking paths
# EXTRACTED_AUDIO_MP3 = "/kaggle/working/extracted_audio.mp3"
# EXTRACTED_AUDIO_WAV = "/kaggle/working/extracted_audio.wav"
# NEW_VOICEOVER = "/kaggle/working/new_ai_voiceover.wav"

# # 4b. Extract the true audio track from the downloaded Reel via FFmpeg
# print("-> Isolating original audio track matrix...")
# subprocess.run(["ffmpeg", "-y", "-i", output_path, "-q:a", "0", "-map", "a", EXTRACTED_AUDIO_MP3], check=True, capture_output=True)

# # Convert to standard uncompressed WAV format for the local transcription engine
# subprocess.run(["ffmpeg", "-y", "-i", EXTRACTED_AUDIO_MP3, EXTRACTED_AUDIO_WAV], check=True, capture_output=True)

# # 4c. Transcribe the original speech using local CPU execution (Bypasses CUDA bugs)
# print("-> Initializing CPU speech-to-text transcription engine...")
# recognizer = sr.Recognizer()
# extracted_text = ""

# try:
#     with sr.AudioFile(EXTRACTED_AUDIO_WAV) as source:
#         audio_data = recognizer.record(source)
#         # Uses Google's free public web speech API gateway to extract exact words
#         extracted_text = recognizer.recognize_google(audio_data)
#     print(f"📝 SUCCESS! Transcribed original video script: \"{extracted_text}\"")
# except Exception as e:
#     print(f"⚠️ Speech API failed or audio was silent: {e}")
#     # Fallback only if the original audio track cannot be transcribed
#     extracted_text = "Check out this amazing video!"
#     print(f"📋 Using safety text fallback: \"{extracted_text}\"")

# # 4d. Run Edge-TTS natively to build the professional human voice file
# print("-> Querying Edge-TTS cloud service for professional narration...")
# sanitized_text = extracted_text.replace('"', '').replace("'", "").strip()
# selected_voice = "en-US-ChristopherNeural"

# async def generate_edge_voice():
#     import edge_tts
#     communicate = edge_tts.Communicate(sanitized_text, selected_voice)
#     await communicate.save(NEW_VOICEOVER)

# asyncio.run(generate_edge_voice())
# print("✅ Professional Edge-TTS voice track generated.")

# # 4e. DYNAMIC SPEED CALCULATION ENGINE
# print("⚡ Calculating precise speed normalization adjustments...")

# def get_duration(file_path):
#     cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {file_path}"
#     return float(subprocess.check_output(cmd, shell=True).decode().strip())

# # Fetch durations down to the millisecond
# orig_duration = get_duration(output_path)
# tts_duration = get_duration(NEW_VOICEOVER)

# # Calculate exactly how much we need to speed up/slow down the TTS voice to match the video length
# speed_factor = tts_duration / orig_duration

# # FFmpeg atempo boundaries rules: Must stay between 0.5 and 2.0
# if speed_factor < 0.5: speed_factor = 0.5
# if speed_factor > 2.0: speed_factor = 2.0

# print(f"⏱️ Original Video Duration: {orig_duration:.2f}s")
# print(f"⏱️ Raw Voiceover Duration: {tts_duration:.2f}s")
# print(f"⏩ Required Voiceover Speed Factor: {speed_factor:.2f}x")

# # ==========================================
# # 5. GPU-ACCELERATED PROCEDURAL VISUAL EDITING STACK
# # ==========================================
# print("🎬 Stacking randomized filters and rendering vertical layout via NVIDIA NVENC GPU...")

# styles = [
#     "eq=contrast=1.05:brightness=0.01:saturation=1.02:gamma=0.97",
#     "curves=m='0/0 0.25/0.18 0.5/0.5 0.75/0.82 1/1':r='0/0 0.5/0.42 1/1':b='0/0 0.4/0.58 1/1'",
#     "eq=contrast=0.95:brightness=0.02:saturation=0.92:gamma=1.04"
# ]
# chosen_style = random.choice(styles)

# effects = [
#     "zoompan=z='min(zoom+0.003,1.12)':x='iw/2-iw/zoom/2+sin(time*2.5)*6':y='ih/2-ih/zoom/2':d=1",
#     "convolution='-1 -1 -1 -1 9 -1 -1 -1 -1',eq=contrast=1.06:brightness=0.01",
#     "hue='H=2.5*PI*t:s=1.03'"
# ]
# chosen_effect = random.choice(effects)

# # Setup 9:16 portrait layout canvas (Safe unmirrored captions + blurred backdrop wallpaper + transparent dust/grain noise + custom brand watermark)
# filter_complex_string = (
#     f"[0:v]scale=1080:1920,boxblur=25:5,{chosen_effect}[bg];"
#     f"[0:v]scale=918:1632,{chosen_style}[main];"
#     f"[bg][main]overlay=(W-w)/2:(H-h)/2[merged];"
#     f"[merged]noise=alls=7:allf=t+u[grained];"
#     f"[grained]drawtext=text='@AWRAM':x=(w-tw)/2:y=80:fontsize=40:fontcolor=white@0.55:box=1:boxcolor=black@0.25[v];"
#     f"[1:a]atempo={speed_factor}[speed_synced_audio]"
# )

# # GPU ACCELERATION: Leverages NVIDIA NVENC T4 Hardware Video Encoder directly
# ffmpeg_cmd = [
#     "ffmpeg", "-y", 
#     "-hwaccel", "cuda",         # Initialize CUDA hardware acceleration gates
#     "-i", output_path,          # Original video matrix layout
#     "-i", NEW_VOICEOVER,         # Raw Edge-TTS track
#     "-filter_complex", filter_complex_string,
#     "-map", "[v]", 
#     "-map", "[speed_synced_audio]", # Map the speed-corrected narration track
#     "-c:v", "h264_nvenc",       # Force NVIDIA NVENC Hardware Video Encoder GPU
#     "-preset", "p4",            # High-performance hardware preset mapping
#     "-cq", "20",                # Maintain perfect clarity for text and borders
#     "-c:a", "aac",              
#     "-b:a", "128k",
#     "-shortest",                # Ensure no trailing dead space
#     OUTPUT_VIDEO
# ]

# res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
# if res.returncode != 0:
#     print(f"❌ FFmpeg transformative execution crashed: {res.stderr}")
#     raise RuntimeError("FFmpeg Pipeline Failure")
# print(f"🚀 GPU Render Complete! Video Saved: {OUTPUT_VIDEO}")


# # ==========================================
# # 5. UPLOAD TO YOUTUBE
# # ==========================================
# print("📤 Uploading to YouTube...")
# yt_url = None
# upload_success = False
# try:
#     creds = Credentials(token=None, refresh_token=YT_REFRESH_TOKEN,
#                         token_uri="https://oauth2.googleapis.com/token",
#                         client_id=YT_CLIENT_ID, client_secret=YT_CLIENT_SECRET,
#                         scopes=["https://www.googleapis.com/auth/youtube.upload"])
#     if creds.expired: creds.refresh(Request())
    
#     youtube = build("youtube", "v3", credentials=creds)
#     body = {
#         "snippet": {"title": pipeline.get("youtube_title", "AI Tip #shorts"),
#                     "description": pipeline.get("youtube_description", ""),
#                     "tags": pipeline.get("youtube_tags", ["AI", "Shorts"])},
#         "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
#     }
#     request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=MediaFileUpload(OUTPUT_VIDEO, chunksize=-1, resumable=True))
#     response = request.execute()
#     yt_url = f"https://www.youtube.com/watch?v={response['id']}"
#     upload_success = True
#     print(f"🎉 YouTube Success: {yt_url}")
# except Exception as e:
#     print(f"⚠️ Upload failed (video saved locally): {e}")

# # ==========================================
# # 6. UPDATE GITHUB LEDGER
# # ==========================================
# print("🔄 Updating GitHub ledger...")
# try:
#     led_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/reel_queue.json"
#     headers_gh = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
#     resp_gh = requests.get(led_url, headers=headers_gh)
#     current = json.loads(requests.utils.b64decode(resp_gh.json()["content"]).decode())
    
#     # Safely convert time formats
#     from datetime import datetime, timezone
    
#     for entry in current.get('processed', []):
#         if entry['url'] == reel_url and entry.get('status') == 'in_progress':
#             entry['status'] = 'success' if upload_success else 'failed'
#             if yt_url: entry['youtube_url'] = yt_url
#             entry['completed_at'] = datetime.now(timezone.utc).isoformat()
#             break
            
#     new_content = requests.utils.b64encode(json.dumps(current).encode()).decode()
#     requests.put(led_url, headers=headers_gh, json={"message": "Auto: Updated reel status", "content": new_content, "sha": resp_gh.json()["sha"]})
#     print("✅ Ledger updated.")
# except Exception as e:
#     print(f"⚠️ Ledger warning: {e}")

# print("\n🏆 PIPELINE COMPLETE!")




# %% [code]
# %% [code]
# %% [code]
import subprocess
import sys
subprocess.run("apt-get update -qq && apt-get install -y -qq ffmpeg > /dev/null", shell=True, check=True)

packages = [
    "requests",
    "torch",
    "transformers",
    "scipy",
    "accelerate",
    "google-api-python-client",
    "google-auth-oauthlib",
    "google-auth-httplib2",
    "instaloader",
    "edge-tts",
    "groq"
]

subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + packages)

print("✅ Dependencies installed. Ready for main script.")

#!/usr/bin/env python3
# production_pipeline.py
# Fully Automated YouTube Shorts Engine: Download → Visual Transformation → Upload → Ledger Update
import os, json, re, requests, subprocess, time, random, torch
from kaggle_secrets import UserSecretsClient
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# ==========================================
# 1. CONFIG & SECRETS
# ==========================================
print("🔐 Loading environment & secrets...")
secrets = UserSecretsClient()
GH_TOKEN = secrets.get_secret("GH_TOKEN")
YT_CLIENT_ID = secrets.get_secret("YOUTUBE_CLIENT_ID")
YT_CLIENT_SECRET = secrets.get_secret("YOUTUBE_CLIENT_SECRET")
YT_REFRESH_TOKEN = secrets.get_secret("YOUTUBE_REFRESH_TOKEN")

GITHUB_USER = os.environ.get("GITHUB_USER", "My-Memory-2008")  # Auto-updates via env or default
GITHUB_REPO = "content-factory-orchestrator"
BRANCH = "main"

WORKING_DIR = "/kaggle/working"
RAW_DIR = os.path.join(WORKING_DIR, "raw_video")
PIPELINE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/refs/heads/{BRANCH}/pipeline_data.json"
QUEUE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/refs/heads/{BRANCH}/reel_queue.json"
OUTPUT_VIDEO = os.path.join(WORKING_DIR, "final_youtube_short.mp4")

os.makedirs(RAW_DIR, exist_ok=True)

# ==========================================
# 2. FETCH PIPELINE DATA
# ==========================================
print("🌐 Fetching pipeline_data.json...")
resp = requests.get(PIPELINE_URL, timeout=30)
resp.raise_for_status()
pipeline = resp.json()

reel_url = pipeline.get("reel_url")
shortcode = pipeline.get("shortcode")
username = pipeline.get("username", "unknown")
print(f"🎯 Target: {reel_url} | Shortcode: {shortcode}")

# ==========================================
# 3. DOWNLOAD REEL (Direct CDN + Fallback)
# ==========================================
print("📥 Downloading video...")
video_url = None
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "X-IG-App-ID": "936619743392459"
}

try:
    # Method 1: Instagram Public API
    resp = requests.get(f"https://www.instagram.com/api/v1/media/{shortcode}/?__a=1&__d=dis", headers=headers, timeout=30)
    if resp.status_code == 200 and 'items' in resp.json():
        video_url = resp.json()['items'][0].get('video_versions', [{}])[0].get('url')
except Exception as e:
    print(f"⚠️ API fetch failed: {e}")

# Method 2: Instaloader Fallback
if not video_url:
    import instaloader
    L = instaloader.Instaloader(download_videos=False, download_pictures=False)
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        video_url = post.video_url
    except Exception as e:
        raise RuntimeError(f"❌ All download methods failed: {e}")

print(f"⬇️ Downloading from CDN...")
v_resp = requests.get(video_url, stream=True, timeout=120)
v_resp.raise_for_status()
output_path = os.path.join(RAW_DIR, f"{username}_{shortcode}.mp4")
with open(output_path, 'wb') as f:
    for chunk in v_resp.iter_content(chunk_size=8192):
        if chunk: f.write(chunk)
print(f"✅ Downloaded: {os.path.basename(output_path)} ({os.path.getsize(output_path)//1024} KB)")



# ==========================================
# 4. STEP 1: EXECUTE ALL VIDEO EDITING TRANSFORMATIONS FIRST
# ==========================================
print("🚀 Step 1: Initiating full visual editing transformation canvas...")

# Define internal rendering layer workspace file paths explicitly
EDITED_SOURCE_ONLY = "/kaggle/working/edited_source_only.mp4"
STANDARDIZED_CAT_ONLY = "/kaggle/working/standardized_cat_only.mp4"
OUTPUT_VIDEO = "/kaggle/working/final_youtube_short.mp4"

# Raw audio tracking layers to force absolute sound mapping parameters
AUDIO1_WAV = "/kaggle/working/track1.wav"
AUDIO2_WAV = "/kaggle/working/track2.wav"
MERGED_AUDIO_WAV = "/kaggle/working/merged_audio.wav"

import gc
try:
    if 'L' in locals(): del L
    if 'post' in locals(): del post
except Exception:
    pass
gc.collect()
torch.cuda.empty_cache()

import cv2
import pytesseract
from pytesseract import Output

# --- AI OCR CHECKPOINT: USERNAME WATERMARK REMOVER ---
print("👁️ Scanning frame layers for creator username text signatures...")
cap = cv2.VideoCapture(output_path)
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
sample_frames = [int(frame_count * 0.15), int(frame_count * 0.45), int(frame_count * 0.75)]
text_watermark_box = None
clean_username_target = username.lower().strip()

for idx in sample_frames:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ret, frame = cap.read()
    if not ret: continue
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ocr_data = pytesseract.image_to_data(gray_frame, output_type=Output.DICT)
    
    for i in range(len(ocr_data['text'])):
        detected_word = str(ocr_data['text'][i]).lower().strip()
        if clean_username_target in detected_word or (len(detected_word) > 3 and detected_word in clean_username_target):
            x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
            text_watermark_box = (max(0, x-15), max(0, y-10), w+30, h+20)
            break
    if text_watermark_box: break
cap.release()

if text_watermark_box:
    x, y, w, h = text_watermark_box
    print(f"🎯 Watermark Matched! Scrubbing region -> X:{x}, Y:{y}, W:{w}, H:{h}")
    CLEAN_INPUT_STAGE1 = "/kaggle/working/ocr_cleaned_source.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", output_path, "-vf", f"delogo=x={x}:y={y}:w={w}:h={h}", "-c:a", "copy", CLEAN_INPUT_STAGE1], check=True, capture_output=True)
else:
    print("✨ Clean Layout Check! Bypassing OCR erasure step.")
    CLEAN_INPUT_STAGE1 = output_path

# --- APPLY 9:16 PORTRAIT VISUAL EDITING FILTER STACK ---
styles = [
    "eq=contrast=1.05:brightness=0.01:saturation=1.02:gamma=0.97",
    "curves=m='0/0 0.25/0.18 0.5/0.5 0.75/0.82 1/1'",
    "eq=contrast=0.95:brightness=0.02:saturation=0.92:gamma=1.04"
]
effects = [
    "convolution='-1 -1 -1 -1 9 -1 -1 -1 -1',eq=contrast=1.06:brightness=0.01",
    "hue='H=0.1*PI*t:s=1.03'",
    "eq=contrast=1.1:brightness=0.02:saturation=1.05"
]
chosen_style, chosen_effect = random.choice(styles), random.choice(effects)

filter_complex_editing = (
    f"[0:v]scale=1080:1920,boxblur=25:5,{chosen_effect}[bg];"
    f"[0:v]scale=918:1632,{chosen_style}[main_scaled];"
    f"[bg][main_scaled]overlay=(W-w)/2:(H-h)/2,setsar=1[processed_source];"
    f"[processed_source]noise=alls=7:allf=t+u[grained];"
    f"[grained]drawtext=text='@AWRAM':x=(w-tw)/2:y=80:fontsize=40:fontcolor=white@0.55:box=1:boxcolor=black@0.25[v]"
)

# Render Step 1: Fully process video transformations into constant 30fps container lanes
ffmpeg_editing = [
    "ffmpeg", "-y", "-hwaccel", "cuda", 
    "-i", CLEAN_INPUT_STAGE1,          
    "-filter_complex", filter_complex_editing, 
    "-map", "[v]",      
    "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20", "-r", "30", "-pix_fmt", "yuv420p",
    EDITED_SOURCE_ONLY
]

res1 = subprocess.run(ffmpeg_editing, capture_output=True, text=True)
if res1.returncode != 0:
    print(f"❌ Editing phase crashed: {res1.stderr}")
    raise RuntimeError("FFmpeg Editing Canvas Failure")
print("✅ Step 1 Complete: Visual layers processed successfully.")




## ==========================================
# 4b. MULTIMODAL VISION AI VIRAL SEO GENERATOR (NO REPEATS)
# ==========================================
print("🧠 Activating Cloud Vision AI Engine via Google GenAI...")
import cv2
import json
import os
from PIL import Image

SEO_MANIFEST_PATH = "/kaggle/working/seo_metadata.json"
TEMP_FRAME_PATH = "/kaggle/working/seo_temp_frame.jpg"

# Safety default fallback metadata structure
seo_metadata = {
    "title": "Most Oddly Satisfying ASMR Challenge! 🤯 #shorts",
    "description": "Wait till the end for the funny cat reaction loop! Original concept inspired by creator. #shorts #asmr",
    "tags": ["satisfying", "asmr", "shorts", "relaxing"]
}

# Fetch your secure environment token out of Kaggle User Secrets Vault
# Make sure you have a secret named "GEMINI_API_KEY" set up in your Kaggle notebook!
gemini_key = secrets.get_secret("GEMINI_API_KEY")

if gemini_key:
    try:
        from google import genai
        from google.genai import types
        
        # Initialize the official secure Google GenAI Client
        client = genai.Client(api_key=gemini_key.strip())
        
        # 1. Capture a mid-timeline frame directly from your edited source video file
        print(f"👁️ Extracting frame data matrix for structural visual analysis from: {EDITED_SOURCE_ONLY}")
        cap = cv2.VideoCapture(EDITED_SOURCE_ONLY)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_count * 0.45)) # Grab frame right in the middle of action
        ret, frame = cap.read()
        cap.release()

        if ret:
            # Save the frame image locally to pass to the Vision API node
            cv2.imwrite(TEMP_FRAME_PATH, frame)
            pil_image = Image.open(TEMP_FRAME_PATH)
            
            print("📡 Uploading video frame to Gemini-2.5 Vision cluster for deep analysis...")
            
            seo_prompt = (
                f"You are a viral YouTube Shorts master growth hacker specializing in high-retention Oddly Satisfying and ASMR niches. "
                f"Analyze this visual frame screenshot taken from a vertical loop video created by @{username}.\n\n"
                f"Tasks:\n"
                f"1. YOUTUBE_TITLE: Write a highly clickable title (Max 65 characters) describing the satisfying action visible in the image. End strictly with #shorts.\n"
                f"2. YOUTUBE_DESCRIPTION: Write an engaging 3-sentence description. Sentence 1 is a witty hook about what is happening in this loop. "
                f"Sentence 2 states why this unique ASMR content is completely addictive. Sentence 3 is an organic CTA to subscribe. Include: \"Original concept inspired by @{username}\". Append viral hashtags.\n"
                f"3. YOUTUBE_TAGS: Provide a clean array of exactly 6 high-traffic trending keywords describing the objects or materials visible in the image.\n\n"
                f"Return your response STRICTLY as a raw JSON object with keys 'youtube_title', 'youtube_description', and 'youtube_tags'. Do not include markdown ticks, 'json' headings, or introductory conversational filler text."
            )

            # Fire the high-speed multimodal generation query
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[pil_image, seo_prompt]
            )
            
            # Clean response boundaries of potential text wrappers cleanly before unpacking
            clean_json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            ai_seo_data = json.loads(clean_json_text)
            
            seo_metadata = {
                "title": ai_seo_data.get('youtube_title', seo_metadata["title"]),
                "description": ai_seo_data.get('youtube_description', seo_metadata["description"]),
                "tags": ai_seo_data.get('youtube_tags', seo_metadata["tags"])
            }
            print(f"🎉 SUCCESS! Fresh Visual SEO Generated via Gemini -> Title: \"{seo_metadata['title']}\"")
            
            # Cleanup temp file from disk partition
            if os.path.exists(TEMP_FRAME_PATH):
                os.remove(TEMP_FRAME_PATH)
        else:
            raise RuntimeError("Frame capture extraction failed.")

    except Exception as vision_error:
        print(f"⚠️ Cloud vision block failed, using system fallback arrays: {vision_error}")
else:
    print("⚠️ GEMINI_API_KEY secret missing in Kaggle vault. Bypassing cloud vision block.")

# Force a memory purge to ensure the GPU is 100% clean for your upcoming video processing stages
import torch
torch.cuda.empty_cache()

# Save metadata manifest file to drive partition for Section 6 upload mapping
with open(SEO_MANIFEST_PATH, 'w') as f:
    json.dump(seo_metadata, f, indent=2)



# ==========================================
# 5. STEP 2: SELECT AND CONVERT THE CAT VIDEO STRUCTURE
# ==========================================
print("🎬 Step 2: Selecting random reaction clip and matching visual parameters exactly...")

cat_dataset_dir = "/kaggle/input/datasets/muhammadasjad2008/cat-reactions-vault"
if os.path.exists(cat_dataset_dir):
    valid_clips = [os.path.join(root, f) for root, _, files in os.walk(cat_dataset_dir) for f in files if f.endswith('.mp4')]
    chosen_cat_file = random.choice(valid_clips) if valid_clips else output_path
else:
    chosen_cat_file = output_path
print(f"🐱 Selected Cat Reaction Asset: {chosen_cat_file}")

# Normalize the cat video track alone down to constant 30fps frames 
ffmpeg_standardize_cat = [
    "ffmpeg", "-y", "-hwaccel", "cuda",
    "-i", chosen_cat_file,
    "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
    "-an", # Drop audio stream temporarily from the video container to bypass format locks
    "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20", "-r", "30", "-pix_fmt", "yuv420p",
    STANDARDIZED_CAT_ONLY
]
subprocess.run(ffmpeg_standardize_cat, check=True, capture_output=True)
print("✅ Step 2 Complete: Visual video frame timelines safely standardized.")

# ==========================================
# 5b. STEP 3: EXTRACT RAW UNCOMPRESSED AUDIO TRACKS
# ==========================================
print("🎙️ Step 3: Extracting raw uncompressed PCM audio matrices to prevent muting faults...")

def get_duration(file_path):
    cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {file_path}"
    return float(subprocess.check_output(cmd, shell=True).decode().strip())

duration1 = get_duration(EDITED_SOURCE_ONLY)
duration2 = get_duration(STANDARDIZED_CAT_ONLY)

# Convert track 1 audio into raw uncompressed WAV layout
subprocess.run(["ffmpeg", "-y", "-i", CLEAN_INPUT_STAGE1, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", "-t", str(duration1), AUDIO1_WAV], check=True, capture_output=True)

# Convert track 2 audio (cat video) into raw uncompressed WAV layout. If it lacks sound, it pads with silent track layers natively.
try:
    subprocess.run(["ffmpeg", "-y", "-i", chosen_cat_file, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", "-t", str(duration2), AUDIO2_WAV], check=True, capture_output=True)
except Exception:
    print("-> Selected cat clip is audio-less. Generating explicit silent track matrix loop...")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-acodec", "pcm_s16le", "-t", str(duration2), AUDIO2_WAV], check=True, capture_output=True)

# Concat the raw WAV audio arrays back-to-back inside system space
print("🤝 Fusing audio arrays cleanly inside system buffers...")
subprocess.run(["ffmpeg", "-y", "-i", AUDIO1_WAV, "-i", AUDIO2_WAV, "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]", "-map", "[a]", "-acodec", "pcm_s16le", MERGED_AUDIO_WAV], check=True, capture_output=True)
print("✅ Step 3 Complete: Raw audio tracks securely linked without data drops.")

# ==========================================
# 5c. STEP 4: STITCH TIMELINES VIA MULTIPLEX STREAM CONTAINER MAPPING
# ==========================================
print("🎬 Step 4: Stitching completed video containers and injecting the unmuted sound track track loop...")

# Join video blocks cleanly via demuxer tracking list
concat_list_path = "/kaggle/working/concat_list.txt"
with open(concat_list_path, "w") as f:
    f.write(f"file '{EDITED_SOURCE_ONLY}'\n")
    f.write(f"file '{STANDARDIZED_CAT_ONLY}'\n")

TEMP_SILENT_MP4 = "/kaggle/working/temp_silent_output.mp4"
subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", TEMP_SILENT_MP4], check=True, capture_output=True)

# Multiplex the combined uncompressed sound track loop and the video together instantly (Takes 0.4 seconds)
ffmpeg_final_mux = [
    "ffmpeg", "-y",
    "-i", TEMP_SILENT_MP4,
    "-i", MERGED_AUDIO_WAV,
    "-map", "0:v", "-map", "1:a", # Map the full video timeline and the unmuted linked audio track back-to-back
    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
    OUTPUT_VIDEO
]
subprocess.run(ffmpeg_final_mux, check=True, capture_output=True)
print(f"🎉 SUCCESS! Video completely compiled at its exact length with unmuted cat audio: {OUTPUT_VIDEO}")


# ==========================================
# 5. UPLOAD TO YOUTUBE
# ==========================================
print("📤 Uploading to YouTube...")
yt_url = None
upload_success = False
try:
    creds = Credentials(token=None, refresh_token=YT_REFRESH_TOKEN,
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=YT_CLIENT_ID, client_secret=YT_CLIENT_SECRET,
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    if creds.expired: creds.refresh(Request())
    
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": seo_metadata["title"],
            "description": seo_metadata["description"] + "\n\n#shorts #asmr #satisfying #viral",
            "tags": seo_metadata["tags"] + ["shorts", "ShortsFeed"],
            "categoryId": "22"
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=MediaFileUpload(OUTPUT_VIDEO, chunksize=-1, resumable=True))
    response = request.execute()
    yt_url = f"https://www.youtube.com/watch?v={response['id']}"
    upload_success = True
    print(f"🎉 YouTube Success: {yt_url}")
except Exception as e:
    print(f"⚠️ Upload failed (video saved locally): {e}")

# ==========================================
# 6. UPDATE GITHUB LEDGER
# ==========================================
print("🔄 Updating GitHub ledger...")
try:
    led_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/reel_queue.json"
    headers_gh = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    resp_gh = requests.get(led_url, headers=headers_gh)
    current = json.loads(requests.utils.b64decode(resp_gh.json()["content"]).decode())
    
    # Safely convert time formats
    from datetime import datetime, timezone
    
    for entry in current.get('processed', []):
        if entry['url'] == reel_url and entry.get('status') == 'in_progress':
            entry['status'] = 'success' if upload_success else 'failed'
            if yt_url: entry['youtube_url'] = yt_url
            entry['completed_at'] = datetime.now(timezone.utc).isoformat()
            break
            
    new_content = requests.utils.b64encode(json.dumps(current).encode()).decode()
    requests.put(led_url, headers=headers_gh, json={"message": "Auto: Updated reel status", "content": new_content, "sha": resp_gh.json()["sha"]})
    print("✅ Ledger updated.")
except Exception as e:
    print(f"⚠️ Ledger warning: {e}")

print("\n🏆 PIPELINE COMPLETE!")

