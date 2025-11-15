import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Input


from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.utils import class_weight

from imblearn.over_sampling import SMOTE


df = pd.read_csv('https://raw.githubusercontent.com/ncl-iot-team/CSC8112/refs/heads/main/data/PM2.5_labelled_data.csv')
df.head()


df['Quality'].value_counts()


X = df[['Value']]
y = df['Quality']


label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)
class_names = label_encoder.classes_


X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded,
    test_size=0.2,
    random_state=42,
    stratify=y_encoded
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

red_label_index = list(class_names).index('RED')
red_count_train = np.sum(y_train == red_label_index)
k_neighbors = min(5, red_count_train - 1) if red_count_train > 1 else 1 # 'Red' only has 12 samples - Take min. 6

smote = SMOTE(random_state=42, k_neighbors=k_neighbors)
X_train_resampled, y_train_resampled = smote.fit_resample(X_train_scaled, y_train)

model = Sequential([
    Input(shape=(1,)),
    Dense(16, activation='relu'),
    Dropout(0.2),
    Dense(32, activation='relu'),
    Dropout(0.2),
    Dense(3, activation='softmax')
])

model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

print(model.summary())

history = model.fit(
    X_train_resampled,
    y_train_resampled,
    epochs=50,
    batch_size=32,
    validation_data=(X_test_scaled, y_test),
    verbose=1
)

model.save('pm25_model.keras')
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model_quant = converter.convert()
with open('pm25_model.tflite', 'wb') as f:
    f.write(tflite_model_quant)


y_pred_probs = model.predict(X_test_scaled)
y_pred_classes = np.argmax(y_pred_probs, axis=1)
print(classification_report(y_test, y_pred_classes, target_names=class_names))

cm = confusion_matrix(y_test, y_pred_classes)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=class_names, yticklabels=class_names)
plt.title('Confusion Matrix (Test Set)')
plt.xlabel('Predicted Label')
plt.ylabel('True Label')
plt.savefig("confusion_matrix.png")


original_size = os.path.getsize('pm25_model.keras')
tflite_size = os.path.getsize('pm25_model.tflite')

plt.figure(figsize=(6, 4))
sizes = [original_size / 1024, tflite_size / 1024]
labels = ['Original Keras', 'Quantized TFLite']
bar = plt.bar(labels, sizes, color=['blue', 'orange'])
plt.ylabel('Size in KB')
plt.ylim(0, 40)
plt.title('Model Size Comparison')
plt.bar_label(bar, fmt='%.2f KB')
plt.savefig("model_size_comparision.png")

print("Label order:", class_names)
print("Scaler mean_:", scaler.mean_)
print("Scaler scale_:", scaler.scale_)
