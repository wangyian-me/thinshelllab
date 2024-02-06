import taichi as ti
# import torch
import time
# from PIL import Image
import numpy as np
import torch
import os
from agent.traj_opt_single import agent_trajopt
from optimizer.optim import Adam_single
import random
from argparse import ArgumentParser
import matplotlib.pyplot as plt
parser = ArgumentParser()
parser.add_argument('--l', type=int, default=0)
parser.add_argument('--r', type=int, default=5)
parser.add_argument('--iter', type=int, default=10)
parser.add_argument('--lr', type=float, default=0.001)
parser.add_argument('--tot_step', type=int, default=5)
parser.add_argument('--target_dir', type=str, default=None)
parser.add_argument('--load_traj', type=str, default=None)
parser.add_argument('--render_option', type=str, default="Taichi")
args = parser.parse_args()

ti.init(ti.cpu, device_memory_fraction=0.5, default_fp=ti.f64, default_ip=ti.i32, fast_math=False,
        offline_cache=True, offline_cache_max_size_of_files=1024 ** 3,
        offline_cache_cleaning_policy='version')

from Scene_forming import Scene, Body
from geometry import projection_query
from engine.render_engine import Renderer
import linalg
import readfile
from analytic_grad_single import Grad

M = 2
N = 16
k_spring = 1000
nv = M * (N ** 2)
nf = M * 2 * (N - 1) ** 2
# nv = (N**2)
# nf = 2*(N-1)**2
total_m = 0.005 * M
h = 0.005

tot_timestep = args.tot_step
sys = Scene(cloth_size=0.1)
sys.cloths[0].Kb[None] = 200.0
analy_grad = Grad(sys, tot_timestep, sys.elastic_cnt - 1)
adam = Adam_single((tot_timestep, sys.elastic_cnt - 1, 6), args.lr, 0.9, 0.9999, 1e-8)
agent = agent_trajopt(args.tot_step, sys.elastic_cnt - 1, max_moving_dist=0.001)
sys.init_all()
analy_grad.init_mass(sys)
renderer = Renderer(sys, "forming", option=args.render_option)

now_reward = -10000
if args.target_dir is not None:
    target_pos = np.load(args.target_dir)

for ww in range(args.l, args.r):
    save_path = f"../imgs/traj_opt_forming_{ww}"
    # sys.init_pos = [(random.random() - 0.5) * 0.002, (random.random() - 0.5) * 0.002, (random.random() - 0.5) * 0.0006]
    renderer.set_save_dir(save_path)
    print(f"Saving Path: {save_path}")

    sys.reset()
    sys.mu_cloth_elastic[None] = 5.0
    plot_x = []
    plot_y = []

    if args.load_traj is not None:
        agent.traj.from_numpy(np.load(args.load_traj))
        agent.fix_action(0.015)
    adam.reset()
    pos_save_dir = f"../data/forming_pos_save"
    # os.mkdir(pos_save_dir)
    for i in range(args.iter):
        render = False
        if i % 20 == 0:
            render = True
        print("iter: ", i)
        analy_grad.copy_pos(sys, 0)
        obs_list = []
        action_list = []
        start_time = time.time()
        if render:
            renderer.render("0")
        for frame in range(1, tot_timestep):
            # print("frame:", frame)
            agent.get_action(frame)
            # sys.get_observation()
            sys.action(frame, agent.delta_pos, agent.delta_rot)
            # agent.get_action_field(frame)
            # obs_list.append(sys.observation.to_torch('cpu'))
            # action_list.append(agent.tmp_action.to_torch('cpu'))
            sys.time_step(projection_query, frame)
            # np_pos = sys.cloths[0].pos.to_numpy()
            # np.save(os.path.join(pos_save_dir, f"{frame}.npy"), np_pos)
            analy_grad.copy_pos(sys, frame)
            if render:
                renderer.render(str(frame))

        # for ii in range(4):
        #     print(ii, sys.cloths[0].pos[ii])
        if args.target_dir is None:
            np_pos = sys.cloths[0].pos.to_numpy()
            np.save(os.path.join(pos_save_dir, f"cloth_pos.npy"), np_pos)
        else:
            end_time = time.time()
            print("tot_time:", end_time - start_time)
            tot_reward = sys.compute_reward(target_pos)
            # if tot_reward > now_reward:
            #     now_reward = tot_reward
            #     data_path = f"../data/data_traj_opt_fold_{ww}"
            #     if not os.path.exists(data_path):
            #         os.mkdir(data_path)
            #     for frame in range(tot_timestep - 1):
            #         torch.save({
            #             'obs': obs_list[frame],
            #             'action': action_list[frame]
            #         }, os.path.join(data_path, f"data_{frame + 1}"))

            plot_x.append(i)
            plot_y.append(tot_reward)
            print("total_reward:", plot_y)
            if tot_reward > now_reward:
                now_reward = tot_reward
                np.save(os.path.join(save_path, "best_traj.npy"), agent.traj.to_numpy())
            np.save(os.path.join(save_path, "plot_data.npy"), np.array(plot_y))

        if render:
            renderer.end_rendering(i)

        analy_grad.get_loss_push(sys, target_pos)

        for i in range(tot_timestep - 1, 0, -1):
            # print("back prop step:", i)
            analy_grad.transfer_grad(i, sys, projection_query)
        print("done grad")
        sys.reset()
        adam.step(agent.traj, analy_grad.gripper_grad)
        agent.fix_action(0.015)
        analy_grad.reset()
        # agent.print_traj()
        plt.plot(plot_x, plot_y)
        plt.savefig(os.path.join(save_path, f"plot.png"))