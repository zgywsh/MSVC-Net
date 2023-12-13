# encoding: utf-8
import argparse
import os
import sys
import torch
torch.manual_seed(7)

from layers.triplet_loss import TripletLoss
from layers.center_loss import CenterLoss
import torch.nn as nn

from torch.backends import cudnn

# print(sys.path)
#
sys.path.append('.')
from config import cfg
from data import make_data_loader
from layers import make_loss, make_loss_with_center
from solver import make_optimizer, make_optimizer_with_center, WarmupMultiStepLR
from utils.reid_metric import R1_mAP
from engine.trainer import create_supervised_evaluator
import logging
from engine.inference import inference

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
train_loader, val_loader, num_query, num_classes = make_data_loader(cfg)

def log(dir):
    # 第一步，创建一个logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Log等级总开关  此时是INFO

    # 第二步，创建一个handler，用于写入日志文件
    logfile = dir + '/log.txt'
    fh = logging.FileHandler(logfile, mode='w')  # w覆盖 a 续写
    fh.setLevel(logging.DEBUG)  # 输出到file的log等级的开关

    # 第三步，再创建一个handler，用于输出到控制台
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)  # 输出到console的log等级的开关

    # 第四步，定义handler的输出格式（时间，文件，行数，错误级别，错误提示）
    formatter = logging.Formatter("%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # 第五步，将logger添加到handler里面
    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

###################################################


def train1():

    dir = "./checkpoints and logs/mgn1"

    from modeling.mgn1 import MGN

    logger = log(dir)

    model = MGN(576).to(device)

    optimizer = make_optimizer(cfg, model)
    scheduler = WarmupMultiStepLR(optimizer, cfg.SOLVER.STEPS, cfg.SOLVER.GAMMA, cfg.SOLVER.WARMUP_FACTOR,
                                  cfg.SOLVER.WARMUP_ITERS, cfg.SOLVER.WARMUP_METHOD)
    evaluator = create_supervised_evaluator(model, metrics={
        'r1_mAP': R1_mAP(num_query, max_rank=50, feat_norm=cfg.TEST.FEAT_NORM)}, device=device)

    def train(cfg):
        train_loss = []
        Max =0
        for epoch in range(1,1+cfg.SOLVER.MAX_EPOCHS ):
            print("Epoch:{},lr:{}".format(epoch,scheduler.get_lr()[0]))
            model.train()
            epoch_loss = []

            for batch_idx, (xb, yb, view) in enumerate(train_loader):
                optimizer.zero_grad()
                inputs, target ,view= xb.to(device), yb.to(device),view.to(device)
                outputs = model(inputs)

                loss_fn = TripletLoss(margin=0.3)
                loss_fn2 = nn.CrossEntropyLoss(label_smoothing=0.1)

                losses = [loss_fn(output, target)[0] for output in outputs[1:4]] + \
                         [loss_fn2(output, target) for output in outputs[4:]]


                loss = sum(losses) / len(losses)


                loss.backward()
                optimizer.step()

                epoch_loss.append(loss.item())

                if batch_idx % 100 ==0 :
                    logger.info("Epoch {}: [{}/{}], run_loss:{}".format(epoch, batch_idx, len(train_loader),loss.item()))
                    print("Epoch {}: [{}/{}], loss:{}".format(epoch, batch_idx, len(train_loader),loss.item()))
                    # # print(loss1,loss2)
                    # print("loss:",loss.item())

            scheduler.step()
            epoch_loss_aver=sum(epoch_loss)/len(epoch_loss)
            train_loss.append(epoch_loss_aver)

            evaluator.run(val_loader)
            cmc, mAP = evaluator.state.metrics['r1_mAP']
            logger.info("Epoch: {},Av_Loss: {},mAP: {:.2%}".format(epoch,epoch_loss_aver,mAP))
            for r in [1, 5, 10]:
                logger.info("CMC curve, Rank-{:<3}:{:.2%}".format(r, cmc[r - 1]))
            print("loss:",epoch_loss_aver)
            print("map:",mAP)

            path_state_dict = dir + "/mgn.pkl"
            if mAP >= Max :
                Max = mAP
                print("max",Max)
                net_state_dict = model.state_dict()
                torch.save(net_state_dict, path_state_dict)
            else:
                net_params = torch.load(path_state_dict)
                # 把加载的参数应用到模型中
                model.load_state_dict(net_params, strict=False)

    train(cfg)


def train2():
    dir = "./checkpoints and logs/mgn2"

    from modeling.mgn2 import MGN

    logger = log(dir)

    model = MGN(576).to(device)

    optimizer = make_optimizer(cfg, model)
    scheduler = WarmupMultiStepLR(optimizer, cfg.SOLVER.STEPS, cfg.SOLVER.GAMMA, cfg.SOLVER.WARMUP_FACTOR,
                                  cfg.SOLVER.WARMUP_ITERS, cfg.SOLVER.WARMUP_METHOD)
    evaluator = create_supervised_evaluator(model, metrics={
        'r1_mAP': R1_mAP(num_query, max_rank=50, feat_norm=cfg.TEST.FEAT_NORM)}, device=device)

    def train(cfg):
        train_loss = []
        Max = 0
        for epoch in range(1, 1 + cfg.SOLVER.MAX_EPOCHS):
            print("Epoch:{},lr:{}".format(epoch, scheduler.get_lr()[0]))
            model.train()
            epoch_loss = []

            for batch_idx, (xb, yb, view) in enumerate(train_loader):
                optimizer.zero_grad()
                inputs, target, view = xb.to(device), yb.to(device), view.to(device)
                outputs = model(inputs)

                loss_fn = TripletLoss(margin=0.3)
                loss_fn2 = nn.CrossEntropyLoss(label_smoothing=0.1)

                losses = [loss_fn(output, target)[0] for output in outputs[1:4]] + \
                         [loss_fn2(output, target) for output in outputs[4:]]

                loss = sum(losses) / len(losses)

                loss.backward()
                optimizer.step()

                epoch_loss.append(loss.item())

                if batch_idx % 100 == 0:
                    logger.info(
                        "Epoch {}: [{}/{}], run_loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))
                    print("Epoch {}: [{}/{}], loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))
                    # # print(loss1,loss2)
                    # print("loss:",loss.item())

            scheduler.step()
            epoch_loss_aver = sum(epoch_loss) / len(epoch_loss)
            train_loss.append(epoch_loss_aver)

            evaluator.run(val_loader)
            cmc, mAP = evaluator.state.metrics['r1_mAP']
            logger.info("Epoch: {},Av_Loss: {},mAP: {:.2%}".format(epoch, epoch_loss_aver, mAP))
            for r in [1, 5, 10]:
                logger.info("CMC curve, Rank-{:<3}:{:.2%}".format(r, cmc[r - 1]))
            print("loss:", epoch_loss_aver)
            print("map:", mAP)

            path_state_dict = dir + "/mgn.pkl"
            if mAP >= Max:
                Max = mAP
                print("max", Max)
                net_state_dict = model.state_dict()
                torch.save(net_state_dict, path_state_dict)
            else:
                net_params = torch.load(path_state_dict)
                # 把加载的参数应用到模型中
                model.load_state_dict(net_params, strict=False)

    train(cfg)


def train3():
    dir = "./checkpoints and logs/mgn3"

    from modeling.mgn3 import MGN

    logger = log(dir)

    model = MGN(576).to(device)

    optimizer = make_optimizer(cfg, model)
    scheduler = WarmupMultiStepLR(optimizer, cfg.SOLVER.STEPS, cfg.SOLVER.GAMMA, cfg.SOLVER.WARMUP_FACTOR,
                                  cfg.SOLVER.WARMUP_ITERS, cfg.SOLVER.WARMUP_METHOD)
    evaluator = create_supervised_evaluator(model, metrics={
        'r1_mAP': R1_mAP(num_query, max_rank=50, feat_norm=cfg.TEST.FEAT_NORM)}, device=device)

    def train(cfg):
        train_loss = []
        Max = 0
        for epoch in range(1, 1 + cfg.SOLVER.MAX_EPOCHS):
            print("Epoch:{},lr:{}".format(epoch, scheduler.get_lr()[0]))
            model.train()
            epoch_loss = []

            for batch_idx, (xb, yb, view) in enumerate(train_loader):
                optimizer.zero_grad()
                inputs, target, view = xb.to(device), yb.to(device), view.to(device)
                outputs = model(inputs)

                loss_fn = TripletLoss(margin=0.3)
                loss_fn2 = nn.CrossEntropyLoss(label_smoothing=0.1)

                losses = [loss_fn(output, target)[0] for output in outputs[1:4]] + \
                         [loss_fn2(output, target) for output in outputs[4:]]

                loss = sum(losses) / len(losses)

                loss.backward()
                optimizer.step()

                epoch_loss.append(loss.item())

                if batch_idx % 100 == 0:
                    logger.info(
                        "Epoch {}: [{}/{}], run_loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))
                    print("Epoch {}: [{}/{}], loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))
                    # # print(loss1,loss2)
                    # print("loss:",loss.item())

            scheduler.step()
            epoch_loss_aver = sum(epoch_loss) / len(epoch_loss)
            train_loss.append(epoch_loss_aver)

            evaluator.run(val_loader)
            cmc, mAP = evaluator.state.metrics['r1_mAP']
            logger.info("Epoch: {},Av_Loss: {},mAP: {:.2%}".format(epoch, epoch_loss_aver, mAP))
            for r in [1, 5, 10]:
                logger.info("CMC curve, Rank-{:<3}:{:.2%}".format(r, cmc[r - 1]))
            print("loss:", epoch_loss_aver)
            print("map:", mAP)

            path_state_dict = dir + "/mgn.pkl"
            if mAP >= Max:
                Max = mAP
                print("max", Max)
                net_state_dict = model.state_dict()
                torch.save(net_state_dict, path_state_dict)
            # else:
            #     net_params = torch.load(path_state_dict)
            #     # 把加载的参数应用到模型中
            #     model.load_state_dict(net_params, strict=False)

    train(cfg)


def train4():

    dir = "./checkpoints and logs/mgn4"
    if not os.path.exists(dir):
        # 文件不存在，创建文件
        os.mkdir(dir)

    logger = log(dir)
    from modeling.mgn3 import MGN

    model = MGN(576).to(device)


    evaluator = create_supervised_evaluator(model, metrics={
        'r1_mAP': R1_mAP(num_query, max_rank=50, feat_norm=cfg.TEST.FEAT_NORM)}, device=device)

    cfg.MODEL.METRIC_LOSS_TYPE = 'triplet_center'
    loss_func, center_criterion = make_loss_with_center(cfg, num_classes)  # modified by gu
    optimizer, optimizer_center = make_optimizer_with_center(cfg, model, center_criterion)
    scheduler = WarmupMultiStepLR(optimizer, cfg.SOLVER.STEPS, cfg.SOLVER.GAMMA, cfg.SOLVER.WARMUP_FACTOR,
                                  cfg.SOLVER.WARMUP_ITERS, cfg.SOLVER.WARMUP_METHOD)




    def train(cfg):
        train_loss = []
        Max = 0
        for epoch in range(1, 1 + cfg.SOLVER.MAX_EPOCHS):
            print("Epoch:{},lr:{}".format(epoch, scheduler.get_lr()[0]))
            model.train()
            epoch_loss = []

            for batch_idx, (xb, yb, view) in enumerate(train_loader):
                optimizer.zero_grad()
                optimizer_center.zero_grad()
                inputs, target, view = xb.to(device), yb.to(device), view.to(device)
                outputs = model(inputs)

                loss_fn = TripletLoss(margin=0.3)
                loss_fn2 = nn.CrossEntropyLoss(label_smoothing=0.1)

                losses = [loss_fn(output, target)[0] for output in outputs[1:4]] + \
                         [loss_fn2(output, target) for output in outputs[4:]]+ \
                        [cfg.SOLVER.CENTER_LOSS_WEIGHT * center_criterion(outputs[0],target)]



                loss = sum(losses) /len(losses)
                loss.backward()
                optimizer.step()
                for param in center_criterion.parameters():
                    param.grad.data *= (1. / cfg.SOLVER.CENTER_LOSS_WEIGHT)
                optimizer_center.step()

                epoch_loss.append(loss.item())

                if batch_idx % 100 == 0:
                    logger.info("Epoch {}: [{}/{}], run_loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))
                    print("Epoch {}: [{}/{}], loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))

            scheduler.step()
            epoch_loss_aver = sum(epoch_loss) / len(epoch_loss)
            train_loss.append(epoch_loss_aver)

            evaluator.run(val_loader)
            cmc, mAP = evaluator.state.metrics['r1_mAP']
            logger.info("Epoch: {},Av_Loss: {},mAP: {:.2%}".format(epoch, epoch_loss_aver, mAP))
            for r in [1, 5, 10]:
                logger.info("CMC curve, Rank-{:<3}:{:.2%}".format(r, cmc[r - 1]))
            print("loss:", epoch_loss_aver)
            print("map:", mAP)

            path_state_dict = dir + "/mgn.pkl"
            if mAP >= Max:
                Max = mAP
                print("max", Max)
                net_state_dict = model.state_dict()
                torch.save(net_state_dict, path_state_dict)
            # else:
            #     net_params = torch.load(path_state_dict)
            #     # 把加载的参数应用到模型中
            #     model.load_state_dict(net_params, strict=False)
    train(cfg)

def train4_0():

    dir = "./checkpoints and logs/mgn4_0"
    if not os.path.exists(dir):
        # 文件不存在，创建文件
        os.mkdir(dir)

    logger = log(dir)
    from modeling.mgn5 import MGN

    model = MGN(576).to(device)


    evaluator = create_supervised_evaluator(model, metrics={
        'r1_mAP': R1_mAP(num_query, max_rank=50, feat_norm=cfg.TEST.FEAT_NORM)}, device=device)

    cfg.MODEL.METRIC_LOSS_TYPE = 'triplet_center'
    loss_func, center_criterion = make_loss_with_center(cfg, num_classes)  # modified by gu
    optimizer, optimizer_center = make_optimizer_with_center(cfg, model, center_criterion)
    cfg.SOLVER.GAMMA = 0.2
    scheduler = WarmupMultiStepLR(optimizer, cfg.SOLVER.STEPS, cfg.SOLVER.GAMMA, cfg.SOLVER.WARMUP_FACTOR,
                                  cfg.SOLVER.WARMUP_ITERS, cfg.SOLVER.WARMUP_METHOD)




    def train(cfg):
        train_loss = []
        Max = 0
        for epoch in range(1, 1 + cfg.SOLVER.MAX_EPOCHS):
            print("Epoch:{},lr:{}".format(epoch, scheduler.get_lr()[0]))
            model.train()
            epoch_loss = []

            for batch_idx, (xb, yb, view) in enumerate(train_loader):
                optimizer.zero_grad()
                optimizer_center.zero_grad()
                inputs, target, view = xb.to(device), yb.to(device), view.to(device)
                outputs = model(inputs)

                loss_fn = TripletLoss(margin=0.3,if_view=True)
                loss_fn2 = nn.CrossEntropyLoss(label_smoothing=0.1)

                losses = [loss_fn(output, target,view_mat=outputs[-2])[0] for output in outputs[1:4]] + \
                         [loss_fn2(output, target) for output in outputs[4:-2]] + \
                         [loss_fn2(outputs[-1], view)]+ \
                        [cfg.SOLVER.CENTER_LOSS_WEIGHT * center_criterion(outputs[0],target)]



                loss = sum(losses) /(len(losses)-1)
                loss.backward()
                optimizer.step()
                for param in center_criterion.parameters():
                    param.grad.data *= (1. / cfg.SOLVER.CENTER_LOSS_WEIGHT)
                optimizer_center.step()

                epoch_loss.append(loss.item())

                if batch_idx % 100 == 0:
                    logger.info("Epoch {}: [{}/{}], run_loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))
                    print("Epoch {}: [{}/{}], loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))

            scheduler.step()
            epoch_loss_aver = sum(epoch_loss) / len(epoch_loss)
            train_loss.append(epoch_loss_aver)

            evaluator.run(val_loader)
            cmc, mAP = evaluator.state.metrics['r1_mAP']
            logger.info("Epoch: {},Av_Loss: {},mAP: {:.2%}".format(epoch, epoch_loss_aver, mAP))
            for r in [1, 5, 10]:
                logger.info("CMC curve, Rank-{:<3}:{:.2%}".format(r, cmc[r - 1]))
            print("loss:", epoch_loss_aver)
            print("map:", mAP)

            path_state_dict = dir + "/mgn.pkl"
            if mAP >= Max:
                Max = mAP
                print("max", Max)
                net_state_dict = model.state_dict()
                torch.save(net_state_dict, path_state_dict)
            # else:
            #     net_params = torch.load(path_state_dict)
            #     # 把加载的参数应用到模型中
            #     model.load_state_dict(net_params, strict=False)
    train(cfg)

def train5():

    dir = "./checkpoints and logs/mgn5"
    logger = log(dir)
    from modeling.mgn5 import MGN

    model = MGN(576).to(device)
    # path_state_dict = dir + "/mgn.pkl"
    # net_params = torch.load(path_state_dict)
    # # 把加载的参数应用到模型中
    # model.load_state_dict(net_params, strict=False)


    evaluator = create_supervised_evaluator(model, metrics={
        'r1_mAP': R1_mAP(num_query, max_rank=50, feat_norm=cfg.TEST.FEAT_NORM)}, device=device)

    cfg.MODEL.IF_WITH_CENTER = 'yes'
    cfg.MODEL.METRIC_LOSS_TYPE = 'triplet_center'
    loss_func, center_criterion = make_loss_with_center(cfg, num_classes)  # modified by gu
    optimizer, optimizer_center = make_optimizer_with_center(cfg, model, center_criterion)
    scheduler = WarmupMultiStepLR(optimizer, cfg.SOLVER.STEPS, cfg.SOLVER.GAMMA, cfg.SOLVER.WARMUP_FACTOR,
                                  cfg.SOLVER.WARMUP_ITERS, cfg.SOLVER.WARMUP_METHOD)


    def train(cfg):
        train_loss = []
        Max = 0
        for epoch in range(1, 1 + cfg.SOLVER.MAX_EPOCHS):
            logger.info("Epoch:{},lr:{}".format(epoch, scheduler.get_lr()[0]))
            print("Epoch:{},lr:{}".format(epoch, scheduler.get_lr()[0]))
            model.train()
            epoch_loss = []

            for batch_idx, (xb, yb, view) in enumerate(train_loader):
                optimizer.zero_grad()
                # optimizer_center.zero_grad()
                inputs, target, view = xb.to(device), yb.to(device), view.to(device)
                outputs = model(inputs)

                loss_fn = TripletLoss(margin=0.3,if_view=True)
                loss_fn2 = nn.CrossEntropyLoss(label_smoothing=0.1)

                losses = [loss_fn(output, target,view_mat=outputs[-2])[0] for output in outputs[1:4]] + \
                         [loss_fn2(output, target) for output in outputs[4:-2]] + \
                         [loss_fn2(outputs[-1], view)]

                loss = sum(losses) / len(losses)
                loss.backward()
                optimizer.step()

                epoch_loss.append(loss.item())

                if batch_idx % 100 == 0:
                    logger.info("Epoch {}: [{}/{}], run_loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))
                    print("Epoch {}: [{}/{}], loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))

            scheduler.step()
            epoch_loss_aver = sum(epoch_loss) / len(epoch_loss)
            train_loss.append(epoch_loss_aver)

            evaluator.run(val_loader)
            cmc, mAP = evaluator.state.metrics['r1_mAP']
            logger.info("Epoch: {},Av_Loss: {},mAP: {:.2%}".format(epoch, epoch_loss_aver, mAP))
            for r in [1, 5, 10]:
                logger.info("CMC curve, Rank-{:<3}:{:.2%}".format(r, cmc[r - 1]))
            print("loss:", epoch_loss_aver)
            print("map:", mAP)

            path_state_dict = dir + "/mgn.pkl"
            if mAP >= Max:
                Max = mAP
                print("max", Max)
                net_state_dict = model.state_dict()
                torch.save(net_state_dict, path_state_dict)
    train(cfg)

def train5_0():

    dir = "./checkpoints and logs/mgn5_0"

    if not os.path.exists(dir):
        # 文件不存在，创建文件
        os.mkdir(dir)
    logger = log(dir)
    from modeling.mgn5 import MGN

    model = MGN(576).to(device)
    # path_state_dict = dir + "/mgn.pkl"
    # net_params = torch.load(path_state_dict)
    # # 把加载的参数应用到模型中
    # model.load_state_dict(net_params, strict=False)

    cfg.SOLVER.BASE_LR = 2e-5
    evaluator = create_supervised_evaluator(model, metrics={
        'r1_mAP': R1_mAP(num_query, max_rank=50, feat_norm=cfg.TEST.FEAT_NORM)}, device=device)

    cfg.MODEL.IF_WITH_CENTER = 'yes'
    cfg.MODEL.METRIC_LOSS_TYPE = 'triplet_center'
    loss_func, center_criterion = make_loss_with_center(cfg, num_classes)  # modified by gu
    optimizer, optimizer_center = make_optimizer_with_center(cfg, model, center_criterion)
    #
    # scheduler = WarmupMultiStepLR(optimizer, (15,25,35,45), 0.1, cfg.SOLVER.WARMUP_FACTOR,
    #                               15, cfg.SOLVER.WARMUP_METHOD)
    scheduler = WarmupMultiStepLR(optimizer, (20,25,35,45), cfg.SOLVER.GAMMA, cfg.SOLVER.WARMUP_FACTOR,
                                  cfg.SOLVER.WARMUP_ITERS, cfg.SOLVER.WARMUP_METHOD)


    def train(cfg):
        train_loss = []
        Max = 0
        for epoch in range(1, 1 + cfg.SOLVER.MAX_EPOCHS):
            logger.info("Epoch:{},lr:{}".format(epoch, scheduler.get_lr()[0]))
            print("Epoch:{},lr:{}".format(epoch, scheduler.get_lr()[0]))
            model.train()
            epoch_loss = []

            for batch_idx, (xb, yb, view) in enumerate(train_loader):
                # if batch_idx % 2 == 0:
                optimizer.zero_grad()
                # optimizer_center.zero_grad()
                inputs, target, view = xb.to(device), yb.to(device), view.to(device)
                outputs = model(inputs)

                loss_fn = TripletLoss(margin=0.3,if_view=True)
                loss_fn2 = nn.CrossEntropyLoss(label_smoothing=0.1)
                # loss_fn3 = nn.CrossEntropyLoss()

                losses = [loss_fn(output, target,view_mat=outputs[-2])[0] for output in outputs[1:4]] + \
                         [loss_fn2(output, target) for output in outputs[4:-2]] + \
                         [loss_fn2(outputs[-1], view)]

                loss = sum(losses) / len(losses)
                loss.backward()
                # if (batch_idx+1) % 2 == 0:
                optimizer.step()


                epoch_loss.append(loss.item())

                if batch_idx % 100 == 0:
                    logger.info("Epoch {}: [{}/{}], run_loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))
                    print("Epoch {}: [{}/{}], loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))

            scheduler.step()
            epoch_loss_aver = sum(epoch_loss) / len(epoch_loss)
            train_loss.append(epoch_loss_aver)

            evaluator.run(val_loader)
            cmc, mAP = evaluator.state.metrics['r1_mAP']
            logger.info("Epoch: {},Av_Loss: {},mAP: {:.2%}".format(epoch, epoch_loss_aver, mAP))
            for r in [1, 5, 10]:
                logger.info("CMC curve, Rank-{:<3}:{:.2%}".format(r, cmc[r - 1]))
            print("loss:", epoch_loss_aver)
            print("map:", mAP)

            path_state_dict = dir + "/mgn.pkl"
            if mAP >= Max:
                Max = mAP
                print("max", Max)
                net_state_dict = model.state_dict()
                torch.save(net_state_dict, path_state_dict)
            # else:
            #     net_params = torch.load(path_state_dict)
            #     # 把加载的参数应用到模型中
            #     model.load_state_dict(net_params, strict=False)
    train(cfg)

def train6():

    dir = "./checkpoints and logs/mgn6"
    if not os.path.exists(dir):
        # 文件不存在，创建文件
        os.mkdir(dir)
    logger = log(dir)
    from modeling.mgn5 import MGN

    model = MGN(576).to(device)
    # path_state_dict = dir + "/mgn.pkl"
    # net_params = torch.load(path_state_dict)
    # # 把加载的参数应用到模型中
    # model.load_state_dict(net_params, strict=False)


    evaluator = create_supervised_evaluator(model, metrics={
        'r1_mAP': R1_mAP(num_query, max_rank=50, feat_norm=cfg.TEST.FEAT_NORM)}, device=device)

    cfg.MODEL.IF_WITH_CENTER = 'yes'
    cfg.MODEL.METRIC_LOSS_TYPE = 'triplet_center'
    loss_func, center_criterion = make_loss_with_center(cfg, num_classes)  # modified by gu
    optimizer, optimizer_center = make_optimizer_with_center(cfg, model, center_criterion)
    #
    # scheduler = WarmupMultiStepLR(optimizer, (15,25,35,45), 0.1, cfg.SOLVER.WARMUP_FACTOR,
    #                               15, cfg.SOLVER.WARMUP_METHOD)
    scheduler = WarmupMultiStepLR(optimizer, cfg.SOLVER.STEPS, cfg.SOLVER.GAMMA, cfg.SOLVER.WARMUP_FACTOR,
                                  cfg.SOLVER.WARMUP_ITERS, cfg.SOLVER.WARMUP_METHOD)


    def train(cfg):
        train_loss = []
        Max = 0
        for epoch in range(1, 1 + cfg.SOLVER.MAX_EPOCHS):
            logger.info("Epoch:{},lr:{}".format(epoch, scheduler.get_lr()[0]))
            print("Epoch:{},lr:{}".format(epoch, scheduler.get_lr()[0]))
            model.train()
            epoch_loss = []

            for batch_idx, (xb, yb, view) in enumerate(train_loader):
                optimizer.zero_grad()
                # optimizer_center.zero_grad()
                inputs, target, view = xb.to(device), yb.to(device), view.to(device)
                outputs = model(inputs)

                loss_fn = TripletLoss(margin=0.3,if_view=True)
                loss_fn2 = nn.CrossEntropyLoss(label_smoothing=0.1)

                losses = [loss_fn(output, target,view_mat=outputs[-2])[0] for output in outputs[1:4]] + \
                         [loss_fn2(output, target) for output in outputs[4:-2]] + \
                         [loss_fn2(outputs[-1], view)]

                loss = sum(losses) / len(losses)
                loss.backward()
                optimizer.step()
                # for param in center_criterion.parameters():
                #     param.grad.data *= (1. / cfg.SOLVER.CENTER_LOSS_WEIGHT)
                # optimizer_center.step()

                epoch_loss.append(loss.item())

                if batch_idx % 100 == 0:
                    logger.info("Epoch {}: [{}/{}], run_loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))
                    print("Epoch {}: [{}/{}], loss:{}".format(epoch, batch_idx, len(train_loader), loss.item()))

            scheduler.step()
            epoch_loss_aver = sum(epoch_loss) / len(epoch_loss)
            train_loss.append(epoch_loss_aver)

            evaluator.run(val_loader)
            cmc, mAP = evaluator.state.metrics['r1_mAP']
            logger.info("Epoch: {},Av_Loss: {},mAP: {:.2%}".format(epoch, epoch_loss_aver, mAP))
            for r in [1, 5, 10]:
                logger.info("CMC curve, Rank-{:<3}:{:.2%}".format(r, cmc[r - 1]))
            print("loss:", epoch_loss_aver)
            print("map:", mAP)

            path_state_dict = dir + "/mgn.pkl"
            if mAP >= Max:
                Max = mAP
                print("max", Max)
                net_state_dict = model.state_dict()
                torch.save(net_state_dict, path_state_dict)
            # else:
            #     net_params = torch.load(path_state_dict)
            #     # 把加载的参数应用到模型中
            #     model.load_state_dict(net_params, strict=False)
    train(cfg)




def main():
    cudnn.benchmark = True
    # train1()
    # train2()
    # train3()
    # train4_0()
    train6()
    train5_0()

    # trainb2()
    # trainb4()



def test():
    cudnn.benchmark = True

    from modeling.mgn6 import MGN
    model = MGN(576).to(device)
    # 导入模型参数
    model_params_path = "/home/wangz/verid/checkpoints and logs/mgn6/mgn.pkl"
    net_params = torch.load(model_params_path)
    # 把加载的参数应用到模型中
    model.load_state_dict(net_params,strict=False)

    evaluator = create_supervised_evaluator(model, metrics={
        'r1_mAP': R1_mAP(num_query, max_rank=50, feat_norm=cfg.TEST.FEAT_NORM)},
                                            device=device)
    evaluator.run(val_loader)
    cmc, mAP = evaluator.state.metrics['r1_mAP']

    print("mAP: {:.2%}".format(mAP))
    for r in [1, 5, 10]:
        print("CMC curve, Rank-{:<3}:{:.2%}".format(r, cmc[r - 1]))





if __name__ == '__main__':
    main()
    # test()
