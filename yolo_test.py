from ultralytics import YOLO
import cv2
import time

print("=== YOLOv8n + クロップ + 高速化 鳥判定 単体テスト ===")

# 1. 超軽量モデル(Nano)に戻す
print("モデル(yolov8n.pt)を読み込み中...")
model = YOLO('yolov8n.pt')

IMAGE_PATH = 'test_bird.jpg'
img = cv2.imread(IMAGE_PATH)

if img is None:
    print("エラー: 画像が見つかりません。")
    exit()

# 2. 画像のクロップ（切り抜き）
h, w = img.shape[:2]
crop_ymin, crop_ymax = int(h * 0.1), int(h * 0.9)
crop_xmin, crop_xmax = int(w * 0.2), int(w * 0.7)
cropped_img = img[crop_ymin:crop_ymax, crop_xmin:crop_xmax]

# 3. AI推論を実行（imgsz=320 で内部解像度を下げて高速化）
print("AI推論を実行中...")
start_time = time.time()
results = model(cropped_img, imgsz=320)
end_time = time.time()

# 4. 結果の解析
bird_detected = False
for result in results:
    boxes = result.boxes
    for box in boxes:
        class_id = int(box.cls[0])
        class_name = model.names[class_id]
        score = int(box.conf[0] * 100)
        
        print(f"- 検出: {class_name} (確信度: {score}%)")
        
        if class_name == 'bird':
            bird_detected = True

# 5. 結果を画像として保存
OUTPUT_PATH = 'result_yolo_fast.jpg'
res_plotted = results[0].plot()
cv2.imwrite(OUTPUT_PATH, res_plotted)

if bird_detected:
    print("★ 鳥を検知しました！")
else:
    print("鳥は検知されませんでした。")

print(f"実際の処理時間: {round((end_time - start_time) * 1000, 1)} ms")
print(f"結果画像を保存しました: {OUTPUT_PATH}")
print("=== テスト終了 ===")