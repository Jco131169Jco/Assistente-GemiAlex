import os, re, json, time, logging, subprocess, webbrowser, platform, sys
try:
    import boto3
    from botocore.config import Config
except Exception:
    print("Instale boto3: pip install -r requirements.txt")
    raise

LOG = logging.getLogger("PCAgent")
LOG.setLevel(logging.INFO)
h1 = logging.StreamHandler(sys.stdout)
h1.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
LOG.addHandler(h1)

QUEUE_URL = os.getenv("SQS_QUEUE_URL","")
REGION    = os.getenv("AWS_REGION","us-east-1")

def load_map():
    path = os.path.join(os.path.dirname(__file__), "commands.json")
    if not os.path.exists(path):
        with open(path,"w",encoding="utf-8") as f:
            json.dump({"patterns":[
                {"match": r"abrir youtube", "action": {"type":"open_url","url":"https://youtube.com"}},
                {"match": r"abrir (https?://\\S+)", "action": {"type":"open_url","url":"{1}"}},
                {"match": r"abrir navegador", "action": {"type":"open_url","url":"https://google.com"}},
                {"match": r"abrir calculadora", "action": {"type":"open_app","windows":"calc.exe","darwin":"open -a Calculator","linux":"gnome-calculator"}}
            ]}, f, ensure_ascii=False, indent=2)
    with open(path,"r",encoding="utf-8") as f: return json.load(f)

def act(action, utter):
    t = action.get("type")
    if t == "open_url":
        url = action.get("url","").replace("{utterance}", utter)
        webbrowser.open(url)
    elif t == "open_app":
        import platform, subprocess
        sysname = platform.system().lower()
        cmd = action.get("windows") if "windows" in sysname else action.get("darwin") if "darwin" in sysname else action.get("linux")
        if cmd: subprocess.Popen(cmd if isinstance(cmd,list) else str(cmd), shell=True)

def main():
    import re
    if not QUEUE_URL:
        print("Defina SQS_QUEUE_URL e AWS_REGION")
        return
    sqs = boto3.client("sqs", region_name=REGION, config=Config(retries={"max_attempts": 5}))
    mapping = load_map()
    print("Agente iniciado. Aguardando comandos...")
    while True:
        try:
            resp = sqs.receive_message(QueueUrl=QUEUE_URL, MaxNumberOfMessages=1, WaitTimeSeconds=20)
            for m in resp.get("Messages", []):
                body = json.loads(m.get("Body","{}"))
                if isinstance(body,str):
                    try: body = json.loads(body)
                    except: body = {"utterance": body}
                utt = (body.get("utterance") or "").strip()
                if utt:
                    print("Recebido:", utt)
                    for rule in mapping.get("patterns", []):
                        pat = rule.get("match")
                        if not pat: continue
                        mm = re.search(pat, utt, re.IGNORECASE)
                        if mm:
                            action = json.loads(json.dumps(rule["action"]))
                            for i,g in enumerate(mm.groups(), start=1):
                                for k,v in list(action.items()):
                                    if isinstance(v,str): action[k] = v.replace(f"{{{i}}}", g)
                            act(action, utt); break
                sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=m["ReceiptHandle"])
        except KeyboardInterrupt:
            break
        except Exception as e:
            LOG.exception("Erro no loop"); time.sleep(2)

if __name__ == "__main__":
    main()