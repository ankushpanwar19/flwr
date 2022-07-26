import torch
import torchvision.transforms as transforms
from torchvision.datasets import CIFAR10
from torch.utils.data import DataLoader

import warnings
from tqdm import tqdm
import numpy as np
warnings.filterwarnings("ignore")
import math

DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(DEVICE)

class ConcatDataset(torch.utils.data.Dataset):
    def __init__(self, *datasets):
        self.datasets = datasets

    def __getitem__(self, i):
        return tuple(d[i] for d in self.datasets)

    def __len__(self):
        return min(len(d) for d in self.datasets)


def load_data():
    """Load CIFAR-10 (training and test set)."""
    transform = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    trainset = CIFAR10("./dataset", train=True, download=True, transform=transform)
    testset = CIFAR10("./dataset", train=False, download=True, transform=transform)

    num_examples = {"trainset": len(trainset), "testset": len(testset)}
    return trainset, testset, num_examples


def load_partition(idx: int,total_partition = 10 ):
    """Load 1/10th of the training and test data to simulate a partition."""
    assert idx in range(total_partition)
    trainset, testset, num_examples = load_data()
    n_train = int(num_examples["trainset"] / total_partition)
    n_test = int(num_examples["testset"] / total_partition)

    train_parition = torch.utils.data.Subset(
        trainset, range(idx * n_train, (idx + 1) * n_train)
    )
    test_parition = torch.utils.data.Subset(
        testset, range(idx * n_test, (idx + 1) * n_test)
    )
    return (train_parition, test_parition)

def load_partition_class(idx: int, total_partition = 10 ):
    """Load 1/10th of the training and test data to simulate a partition."""
    assert idx in range(total_partition)
    trainset, testset, num_examples = load_data()
    # trainset_check, _, _ = load_data()
    idxByClass = []
    for cls in range(10):
        indx = np.array(trainset.targets)==cls
        idxByClass.append(indx)
        # trainset_check.targets = list(np.array(trainset.targets)[idx])
        # trainset_check.data = trainset.data[idx]
        # datasetsByClass.append(trainset_check)  

    n_train = math.ceil(10 / total_partition)
    n_test = math.ceil(10 / total_partition)
    start = idx*n_train
    end = (idx+1)*n_train
    partition_idx=idxByClass[start]
    for i in range(start+1,end):
       partition_idx +=idxByClass[i]
    idx_val = np.where(partition_idx==True)[0]
    train_parition = torch.utils.data.Subset(
        trainset, idx_val
    )
    test_parition = testset

    return (train_parition, test_parition)


def train(net, trainloader, valloader, epochs, device: str = "cpu",testLoader=None):
    """Train the network on the training set."""
    print("Starting training...")
    net.to(device)  # move model to GPU if available
    criterion = torch.nn.CrossEntropyLoss().to(device)
    optimizer = torch.optim.Adam(
        net.parameters(), lr=0.001, weight_decay=1e-4
    )

    for epoch in range(epochs):
        i=0
        running_loss = 0.0
        # print("Starting epoch :",epoch+1)
        # vloss, vacc = test(net, valloader,device=device)
        # print(f"Validation:: Epoch:{epoch}, vloss:{vloss} vacc:{vacc}")
        # if testLoader is not None:
        #     tloss, tacc = test(net, testLoader,device=device)
        #     print(f"Testing:: Epoch:{epoch}, tloss:{tloss} tacc:{tacc}")
        # PATH = f"checkpoints/model_ep{epoch}.pth"
        # torch.save(net.state_dict(), PATH)
        net.train()
        for images, labels in (pbar := tqdm(trainloader)):
            # print(f"Training {epochs} epoch(s) w/ {len(trainloader)} batches each")
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(net(images), labels)
            loss.backward()
            optimizer.step()
            i+=1
            running_loss += loss.item()
            pbar.set_description(f"Loss:{running_loss/i}")
            # if i % 100 == 99:  # print every 100 mini-batches
            #     print("[%d, %5d] loss: %.3f" % (epoch + 1, i + 1, running_loss / 16*20))
            #     running_loss = 0.0
            # break

    # net.to("cpu")  # move model back to CPU

    # train_loss, train_acc = test(net, trainloader,device=device)
    val_loss, val_acc = test(net, valloader,device=device)

    results = {
        "train_loss": 0.0,
        "train_accuracy": 0.0,
        "val_loss": val_loss,
        "val_accuracy": val_acc,
    }
    net.to("cpu")
    return results


def test(net, testloader, steps: int = None, device: str = "cpu"):
    """Validate the network on the entire test set."""
    print("Starting evalutation...")
    net.to(device)  # move model to GPU if available
    criterion = torch.nn.CrossEntropyLoss()
    correct, total, loss = 0, 0, 0.0
    net.eval()
    with torch.no_grad():
        for batch_idx, (images, labels) in enumerate(tqdm(testloader)):
            images, labels = images.to(device), labels.to(device)
            outputs = net(images)
            loss += criterion(outputs, labels).item()
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            # break
            if steps is not None and batch_idx == steps:
                break
    if steps is None:
        loss /= len(testloader.dataset)
    else:
        loss /= total
    accuracy = correct / total
    net.to("cpu")  # move model back to CPU
    return loss, accuracy


def replace_classifying_layer(efficientnet_model, num_classes: int = 10):
    """Replaces the final layer of the classifier."""
    # num_features = efficientnet_model.classifier.fc.in_features
    # efficientnet_model.classifier.fc = torch.nn.Linear(num_features, num_classes)

    num_features = efficientnet_model.classifier[1].in_features
    efficientnet_model.classifier[1] = torch.nn.Linear(num_features, num_classes)


def load_efficientnet(entrypoint: str = "nvidia_efficientnet_b0", classes: int = None):
    """Loads pretrained efficientnet model from torch hub. Replaces final
    classifying layer if classes is specified.
    Args:
        entrypoint: EfficientNet model to download.
                    For supported entrypoints, please refer
                    https://pytorch.org/hub/nvidia_deeplearningexamples_efficientnet/
        classes: Number of classes in final classifying layer. Leave as None to get the downloaded
                 model untouched.
    Returns:
        EfficientNet Model
    Note: One alternative implementation can be found at https://github.com/lukemelas/EfficientNet-PyTorch
    """
    # efficientnet = torch.hub.load(
    #     "NVIDIA/DeepLearningExamples:torchhub", entrypoint, pretrained=True
    # )
    efficientnet = torch.hub.load('pytorch/vision:v0.10.0', 'mobilenet_v2', pretrained=True)

    if classes is not None:
        replace_classifying_layer(efficientnet, classes)
    return efficientnet


def get_model_params(model: "PyTorch Model"):
    """Returns a model's parameters."""
    return [val.cpu().numpy() for _, val in model.state_dict().items()]

def train_central(model,trainset,testset,epochs,device='cpu'):

    validation_split =0.1
    n_valset = int(len(trainset) * validation_split)

    valset = torch.utils.data.Subset(trainset, range(0, n_valset))
    trainset = torch.utils.data.Subset(trainset, range(n_valset, len(trainset)))


    trainLoader = DataLoader(trainset, batch_size=32, shuffle=True)
    valLoader = DataLoader(valset, batch_size=32)
    testLoader = DataLoader(testset, batch_size=32)

    results = train(model, trainLoader, valLoader, epochs, device,testLoader=testLoader)
    print(results)
    loss, accuracy = test(model, testLoader,device=device)
    print(f"Central Training Test Metrics: Loss = {loss} , Acc = {accuracy}")
    

if __name__=="__main__":
    # trainset, testset, num_examples = load_data()
    # model = load_efficientnet(classes=10)
    # train_central(model,trainset,testset,epochs=10,device = DEVICE)
    # load_partition(idx=0)
    trainset, testset = load_partition_class(idx=0,total_partition=2)
    model = load_efficientnet(classes=10)
    train_central(model,trainset,testset,epochs=10,device = DEVICE)
