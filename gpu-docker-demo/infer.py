import os
import sys

import torch
import torchvision
import torchvision.transforms as transforms

from model import Net

DATA_DIR = "data"
CHECKPOINT_PATH = os.path.join("checkpoints", "model.pth")
NUM_SAMPLES = 8

CLASSES = (
    "plane",
    "car",
    "bird",
    "cat",
    "deer",
    "dog",
    "frog",
    "horse",
    "ship",
    "truck",
)


def main():
    if not os.path.exists(CHECKPOINT_PATH):
        print(
            f"No checkpoint found at {CHECKPOINT_PATH}. "
            "Run the container in 'train' mode first: "
            "docker run --gpus all gpu-demo train"
        )
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    net = Net().to(device)
    net.load_state_dict(torch.load(CHECKPOINT_PATH, map_location=device))
    net.eval()

    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )
    testset = torchvision.datasets.CIFAR10(
        root=DATA_DIR, train=False, download=True, transform=transform
    )

    images = torch.stack([testset[i][0] for i in range(NUM_SAMPLES)]).to(device)
    labels = torch.tensor([testset[i][1] for i in range(NUM_SAMPLES)]).to(device)

    with torch.no_grad():
        outputs = net(images)
        _, predicted = torch.max(outputs, 1)

    correct = 0
    for i in range(NUM_SAMPLES):
        actual = CLASSES[labels[i]]
        predicted_label = CLASSES[predicted[i]]
        match = predicted_label == actual
        correct += int(match)
        print(f"sample {i}: predicted={predicted_label} actual={actual}")

    print(f"accuracy on {NUM_SAMPLES} samples: {correct}/{NUM_SAMPLES}")


if __name__ == "__main__":
    main()
