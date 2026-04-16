import pandas as pd
import glob
import torch
import torch.nn as nn
import numpy as np
from sklearn.utils import shuffle

# 1. Load CSVs
dfs = []
for file in glob.glob("dataset/*.csv"):
    df = pd.read_csv(file, header=None)
    if df.shape[1] == 43:
        dfs.append(df)
    else:
        print(f"Skipping {file}, has {df.shape[1]} columns")

if not dfs:
    print("No data found! Check your dataset folder.")
    exit()

data = pd.concat(dfs, ignore_index=True)

# 2. Split features and labels
X = data.iloc[:, :-1].values 
# Convert labels to string immediately to avoid integer vs string KeyErrors
y = data.iloc[:, -1].values.astype(str) 

# 3. Normalize landmarks
def normalize_landmarks(row):
    wrist_x, wrist_y = row[0], row[1]
    norm_row = [(row[i] - wrist_x) for i in range(0, len(row), 2)] + \
               [(row[i] - wrist_y) for i in range(1, len(row), 2)]
    max_val = max(abs(max(norm_row)), abs(min(norm_row)))
    if max_val > 0:
        norm_row = [v / max_val for v in norm_row]
    return norm_row

X_normalized = np.array([normalize_landmarks(row) for row in X])

# 4. Encode labels
labels = {
    "palm": 0, 
    "1": 1, 
    "2": 2, 
    "3": 3, 
    "fist": 4
}

try:
    y_encoded = np.array([labels[label] for label in y])
except KeyError as e:
    print(f"Error: Found a label in CSV not in your dictionary: {e}")
    print(f"Unique labels actually found in your data: {np.unique(y)}")
    exit()

# 5. Shuffle & Augment (with Mirroring!)
X_normalized, y_encoded = shuffle(X_normalized, y_encoded, random_state=42)

def augment_row(row):
    # Small random jitter (translation)
    shift_x = np.random.uniform(-0.02, 0.02, size=21)
    shift_y = np.random.uniform(-0.02, 0.02, size=21)
    new_row = []
    for i in range(21):
        new_row.append(row[i] + shift_x[i])
    for i in range(21, 42):
        new_row.append(row[i] + shift_y[i-21])
    return new_row

def mirror_row(row):
    # The first 21 values are X coordinates. 
    # Multiplying them by -1 flips the hand horizontally.
    mirrored_row = row.copy()
    for i in range(21):
        mirrored_row[i] = -mirrored_row[i]
    return mirrored_row

aug_X, aug_y = [], []
for i in range(len(X_normalized)):
    # 1. Add original data (Right hand)
    aug_X.append(X_normalized[i])
    aug_y.append(y_encoded[i])
    
    # 2. Add mirrored data (mirrored Left hand)
    aug_X.append(mirror_row(X_normalized[i]))
    aug_y.append(y_encoded[i])
    
    # 3. Add a jittered version for variety
    aug_X.append(augment_row(X_normalized[i]))
    aug_y.append(y_encoded[i])

X_tensor = torch.tensor(np.array(aug_X), dtype=torch.float32)
y_tensor = torch.tensor(np.array(aug_y), dtype=torch.long)

# 6. Model Definition
class PoseNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(42, 64)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(0.2)
        self.fc2 = nn.Linear(64, 32)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(0.2)
        self.fc3 = nn.Linear(32, 5)

    def forward(self, x):
        x = self.relu1(self.fc1(x))
        x = self.dropout1(x)
        x = self.relu2(self.fc2(x))
        x = self.dropout2(x)
        return self.fc3(x)

model = PoseNet()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
loss_fn = nn.CrossEntropyLoss()

# 7. Train Loop
epochs = 500
for epoch in range(epochs):
    model.train()
    optimizer.zero_grad()
    preds = model(X_tensor)
    loss = loss_fn(preds, y_tensor)
    loss.backward()
    optimizer.step()

    if epoch % 50 == 0:
        _, predicted_classes = torch.max(preds, 1)
        acc = (predicted_classes == y_tensor).float().mean().item()
        print(f"Epoch {epoch:03d} | Loss: {loss.item():.4f} | Acc: {acc*100:.2f}%")

# 8. Save
torch.save(model.state_dict(), "pose_model.pt")
print("Model saved successfully!")
