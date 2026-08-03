import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

LOG_FILE = "/home/msofk/bird-camera/system_stats.csv"
OUTPUT_IMAGE = "/home/msofk/bird-camera/resource_graph.png"

try:
    # CSVデータの読み込みと日時のパース
    df = pd.read_csv(LOG_FILE)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    
    # グラフの描画設定
    fig, ax1 = plt.subplots(figsize=(10, 5))
    
    # 左軸: 温度 (赤線)
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Temperature (C)', color='tab:red')
    ax1.plot(df['Timestamp'], df['Temperature(C)'], color='tab:red', label='Temp(C)')
    ax1.tick_params(axis='y', labelcolor='tab:red')
    
    # 右軸: CPU使用率 (青線) - 軸を共有
    ax2 = ax1.twinx()  
    ax2.set_ylabel('CPU Usage (%)', color='tab:blue')
    ax2.plot(df['Timestamp'], df['CPU(%)'], color='tab:blue', alpha=0.6, label='CPU(%)')
    ax2.tick_params(axis='y', labelcolor='tab:blue')
    
    # ファンの稼働状況を背景色でハイライト
    fan_on_periods = df[df['Fan_ON'] == 1]
    for _, row in fan_on_periods.iterrows():
        ax1.axvspan(row['Timestamp'], row['Timestamp'], color='orange', alpha=0.3)
        
    # X軸のフォーマットを見やすく調整
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.autofmt_xdate()
    
    plt.title('System Temperature & CPU Load')
    fig.tight_layout()
    
    # 画像として保存
    plt.savefig(OUTPUT_IMAGE)
    print(f"グラフを生成しました: {OUTPUT_IMAGE}")
    
except Exception as e:
    print(f"エラーが発生しました。データが十分に溜まっていない可能性があります: {e}")