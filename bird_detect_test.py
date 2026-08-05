import cv2
import numpy as np
try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    from tflite_runtime.interpreter import Interpreter

# --- 設定 ---
MODEL_PATH = 'detect.tflite'
LABEL_PATH = 'labelmap.txt'
IMAGE_PATH = 'test_bird.jpg'
OUTPUT_PATH = 'result_test.jpg'
THRESHOLD = 0.5  # 確信度（スコア）の閾値（50%以上で検知とする）

def load_labels(path):
    """ラベルマップを読み込む"""
    with open(path, 'r') as f:
        return {i: line.strip() for i, line in enumerate(f.readlines())}

def main():
    print("=== AI鳥判定 単体テスト開始 ===")

    # 1. ラベルの読み込み
    labels = load_labels(LABEL_PATH)
    
    # 2. モデルの初期化
    print(f"モデル({MODEL_PATH})をロード中...")
    interpreter = Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    
    # 入出力テンソルの情報を取得
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    height = input_details[0]['shape'][1]
    width = input_details[0]['shape'][2]

    # 3. テスト画像の読み込みと前処理
    print(f"画像({IMAGE_PATH})を読み込み中...")
    image = cv2.imread(IMAGE_PATH)
    if image is None:
        print("エラー: 画像が見つかりません。パスを確認してください。")
        return

    # --- 【追加】ROI（関心領域）のクロップ ---
    h, w = image.shape[:2]
    # 巣箱周辺（例えば 縦20%〜90%、横20%〜80% の範囲）だけを切り出す
    crop_ymin, crop_ymax = int(h * 0.2), int(h * 0.9)
    crop_xmin, crop_xmax = int(w * 0.2), int(w * 0.8)
    image = image[crop_ymin:crop_ymax, crop_xmin:crop_xmax]
    # ----------------------------------------

    # 描画用のコピーと、モデル入力用のリサイズ＆RGB変換
    draw_image = image.copy()
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image_resized = cv2.resize(image_rgb, (width, height))
    input_data = np.expand_dims(image_resized, axis=0)

    # 4. 推論（AI解析）の実行
    print("AI推論を実行中...")
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()

    # 5. 結果の取得
    boxes = interpreter.get_tensor(output_details[0]['index'])[0] # バウンディングボックス座標
    classes = interpreter.get_tensor(output_details[1]['index'])[0] # クラスID
    scores = interpreter.get_tensor(output_details[2]['index'])[0] # 確信度

    bird_detected = False

    # 6. 結果の解析と判定
    for i in range(len(scores)):
        if scores[i] >= THRESHOLD:
            # クラスIDからラベル名を取得（TFLiteモデルの仕様によりクラスIDは+1される場合があるため調整）
            class_id = int(classes[i])
            class_name = labels.get(class_id + 1, "Unknown")
            score_percent = int(scores[i] * 100)

            print(f"- 検出: {class_name} (確信度: {score_percent}%)")

            # 「鳥（bird）」クラスが含まれているかチェック
            if class_name == 'bird':
                bird_detected = True
                print("★ 鳥を検知しました！")
                
                # 画像に枠とテキストを描画
                ymin, xmin, ymax, xmax = boxes[i]
                im_h, im_w, _ = draw_image.shape
                start_point = (int(xmin * im_w), int(ymin * im_h))
                end_point = (int(xmax * im_w), int(ymax * im_h))
                
                cv2.rectangle(draw_image, start_point, end_point, (0, 255, 0), 2)
                cv2.putText(draw_image, f"{class_name} {score_percent}%", 
                            (start_point[0], start_point[1] - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    if bird_detected:
        cv2.imwrite(OUTPUT_PATH, draw_image)
        print(f"結果画像を保存しました: {OUTPUT_PATH}")
    else:
        print("鳥は検知されませんでした。")

    print("=== テスト終了 ===")

if __name__ == '__main__':
    main()