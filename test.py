from collections import deque


dq = deque(maxlen=5)
for i in range(30):
    dq.append(i)
    print(dq)
