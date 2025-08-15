#!/usr/bin/env python3
import argparse
import os
import random
import string
import time
import threading
import queue
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
import smtplib
from pathlib import Path

BANNER = "SAFE LOCAL EMAIL LOAD TESTER - FOR YOUR OWN TEST SYSTEMS ONLY"

def read_env_file(path=".env"):
    env = {}
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

def random_text(n):
    alphabet = string.ascii_letters + string.digits + " _-.,:;!@#$%^&*()[]{}"
    return "".join(random.choice(alphabet) for _ in range(n))

def build_message(from_addr, to_addr, subject_len, min_bytes, max_bytes, add_attachment=False):
    msg = EmailMessage()
    msg["Message-ID"] = make_msgid()
    msg["Date"] = formatdate(localtime=True)
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = random_text(subject_len)
    body_len = random.randint(min_bytes, max_bytes)
    msg.set_content(random_text(body_len))

    if add_attachment:
        att_len = random.randint(min(256, min_bytes), min(1024 * 64, max_bytes))
        payload = os.urandom(att_len)
        msg.add_attachment(payload, maintype="application", subtype="octet-stream", filename="blob.bin")
    return msg

def worker(task_q, result_q, args):
    # connect per worker to avoid reconnect overhead
    server = smtplib.SMTP(args.smtp_host, args.smtp_port, timeout=10)
    try:
        if args.smtp_starttls:
            server.starttls()
        if args.smtp_user and args.smtp_pass:
            server.login(args.smtp_user, args.smtp_pass)
        while True:
            item = task_q.get()
            if item is None:
                break
            i = item
            try:
                msg = build_message(args.mail_from, args.mail_to, args.subject_len, args.min_bytes, args.max_bytes, args.attachment)
                server.send_message(msg)
                result_q.put(("ok", 1))
            except Exception as e:
                result_q.put(("err", str(e)))
            finally:
                task_q.task_done()
    finally:
        try:
            server.quit()
        except Exception:
            pass

def rate_controller(rate_per_sec):
    # simple token bucket with time sleeps
    if rate_per_sec <= 0:
        return
    time.sleep(1.0 / rate_per_sec)

def main():
    env = read_env_file()
    parser = argparse.ArgumentParser(description=BANNER)
    parser.add_argument("--smtp-host", default=env.get("SMTP_HOST", "127.0.0.1"))
    parser.add_argument("--smtp-port", type=int, default=int(env.get("SMTP_PORT", "1025")))
    parser.add_argument("--smtp-user", default=env.get("SMTP_USER", ""))
    parser.add_argument("--smtp-pass", default=env.get("SMTP_PASS", ""))
    parser.add_argument("--smtp-starttls", action="store_true", help="use STARTTLS if your local test server supports it")
    parser.add_argument("--mail-from", default=env.get("MAIL_FROM", "test@local.test"))
    parser.add_argument("--mail-to", default=env.get("MAIL_TO", "sink@local.test"))
    parser.add_argument("--messages", type=int, default=int(env.get("MESSAGES", "1000")))
    parser.add_argument("--concurrency", type=int, default=int(env.get("CONCURRENCY", "10")))
    parser.add_argument("--rate", type=float, default=float(env.get("RATE", "7")), help="max messages per second overall, 0 = unlimited")
    parser.add_argument("--subject-len", type=int, default=int(env.get("SUBJECT_LEN", "32")))
    parser.add_argument("--min-bytes", type=int, default=int(env.get("MIN_BYTES", "200")))
    parser.add_argument("--max-bytes", type=int, default=int(env.get("MAX_BYTES", "2000")))
    parser.add_argument("--attachment", action="store_true", help="add random binary attachment")
    parser.add_argument("--metrics", default=env.get("METRICS", "metrics.jsonl"), help="path to metrics JSONL")
    args = parser.parse_args()

    tasks = queue.Queue(maxsize=args.concurrency * 2)
    results = queue.Queue()

    workers = []
    for _ in range(args.concurrency):
        t = threading.Thread(target=worker, args=(tasks, results, args), daemon=True)
        t.start()
        workers.append(t)

    start = time.time()
    sent = 0
    errs = 0

    # metrics file
    metrics_path = args.metrics
    mf = open(metrics_path, "w", encoding="utf-8")

    for i in range(args.messages):
        # respect rate limit
        if args.rate > 0:
            rate_controller(args.rate)
        tasks.put(i)

    tasks.join()

    # stop workers
    for _ in workers:
        tasks.put(None)
    for t in workers:
        t.join()

    # drain results
    while not results.empty():
        status, val = results.get()
        if status == "ok":
            sent += val
        else:
            errs += 1
            mf.write('{"event":"error","error":%s}\n' % json.dumps(val))

    elapsed = time.time() - start
    mf.write(json.dumps({
        "event": "summary",
        "sent": sent,
        "errors": errs,
        "concurrency": args.concurrency,
        "elapsed_sec": elapsed,
        "rate_avg": (sent / elapsed) if elapsed > 0 else 0.0
    }) + "\n")
    mf.close()

    print(f"sent={sent} errors={errs} elapsed_sec={elapsed:.2f} avg_msgs_per_sec={(sent/elapsed) if elapsed>0 else 0:.2f}")
    print(f"metrics written to {metrics_path}")
    print("open Mailpit at http://localhost:8025 to inspect captured messages")

if __name__ == "__main__":
    main()