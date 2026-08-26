import time

try:
    print("البرنامج قيد التشغيل... اضغط Ctrl+C للإيقاف.")
    while True:
        time.sleep(1)  # يمنع استهلاك المعالج (CPU) أثناء الانتظار
except KeyboardInterrupt:
        print("\nتم إيقاف البرنامج بنجاح.")
