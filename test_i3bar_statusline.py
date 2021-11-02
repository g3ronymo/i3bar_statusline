import i3bar_statusline
import json


HEADER = { 
        "version": 1,
        "stop_signal": 10,
        "cont_signal": 12,
        "click_events": True,
}

statusline1 = i3bar_statusline.StatusLine(
        i3bar_statusline.TimeBlock('time', 1),
        i3bar_statusline.DateBlock('date', 1)
)
print(json.dumps(HEADER))
print('[')
for i in range(10): 
    statusline1.print()
