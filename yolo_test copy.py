from ultralytics import YOLO
import cv2

print("=== YOLOv8s + クロップ 鳥判定 単体テスト ===")

# 1. モデルを少し賢い「Small(s)」に変更（初回のみ自動ダウンロードされます）
print("モデル(yolov8s.pt)を読み込み中...")
model = YOLO('yolov8s.pt')

# 2. 画像の読み込みとクロップ（切り抜き）
IMAGE_PATH = 'test_bird.jpg'
img = cv2.imread(IMAGE_PATH)

if img is None:
    print("エラー: 画像が見つかりません。")
    exit()

# 画像サイズ（480x640）に合わせて、巣箱周辺を切り抜く
# 縦は上から10%〜90%、横は左から20%〜70%の範囲
h, w = img.shape[:2]
crop_ymin, crop_ymax = int(h * 0.1), int(h * 0.9)
crop_xmin, crop_xmax = int(w * 0.2), int(w * 0.7)
cropped_img = img[crop_ymin:crop_ymax, crop_xmin:crop_xmax]

# 3. AI推論を実行（切り抜いた画像を直接渡す）
print("AI推論を実行中...")
results = model(cropped_img)

# 4. 結果の解析
bird_detected = False
for result in results:
    boxes = result.boxes
    for box in boxes:
        # 検出されたクラスIDを取得し、名前に変換
        class_id = int(box.cls[0])
        class_name = model.names[class_id]
        score = int(box.conf[0] * 100)
        
        print(f"- 検出: {class_name} (確信度: {score}%)")
        
        if class_name == 'bird':
            bird_detected = True

# 5. 結果を画像として保存
OUTPUT_PATH = 'result_yolo_crop.jpg'
res_plotted = results[0].plot()
cv2.imwrite(OUTPUT_PATH, res_plotted)

if bird_detected:
    print("★ 鳥を検知しました！")
else:
    print("鳥は検知されませんでした。")

print(f"結果画像を保存しました: {OUTPUT_PATH}")
print("=== テスト終了 ===")