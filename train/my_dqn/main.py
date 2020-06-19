#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
@author: Gao Fang
@contact: gaofang@cetc.com.cn
@software: PyCharm
@file: main.py
@time: 2018/7/25 0025 10:01
@desc: 
"""

import os
import copy
import numpy as np
from agent.fix_rule_no_att.agent import Agent
from interface import Environment
from train.my_dqn import dqn

import logging
from tensorboardX import SummaryWriter
from collections import deque
MAP_PATH = 'maps/1000_1000_fighter10v10.map'

# RENDER = True
RENDER = False
MAX_EPOCH = 5000
MAX_STEP = 400
BATCH_SIZE = 200
LR = 0.01                   # learning rate
EPSILON = 0.9               # greedy policy
GAMMA = 0.9                 # reward discount
TARGET_REPLACE_ITER = 100   # target update frequency
DETECTOR_NUM = 0
FIGHTER_NUM = 10
COURSE_NUM = 16
ATTACK_IND_NUM = (DETECTOR_NUM + FIGHTER_NUM) * 2 + 1 # long missile attack + short missile attack + no attack
ACTION_NUM = COURSE_NUM * ATTACK_IND_NUM
LEARN_INTERVAL = 100

log_format = "%(asctime)s ==== %(process)d ==== %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format)

if __name__ == "__main__":
    # create blue agent
    blue_agent = Agent()
    # get agent obs type
    red_agent_obs_ind = 'my_dqn'
    blue_agent_obs_ind = blue_agent.get_obs_ind()
    # make env
    env = Environment(MAP_PATH, red_agent_obs_ind, blue_agent_obs_ind, max_step=MAX_STEP, render=RENDER)
    # get map info
    size_x, size_y = env.get_map_size()
    red_detector_num, red_fighter_num, blue_detector_num, blue_fighter_num = env.get_unit_num()
    # set map info to blue agent
    blue_agent.set_map_info(size_x, size_y, blue_detector_num, blue_fighter_num)

    red_detector_action = []
    # fighter_model = dqn.RLFighter(ACTION_NUM)
    e_greedy_increment = 0.0001
    fighter_model = dqn.RLFighter(ACTION_NUM, e_greedy_increment=e_greedy_increment)

    tb_logger = SummaryWriter('./tb_log/', comment='my_dqn')
    recent_episode_res = deque()          # loss: -1, tie: 0, win: 1
    episode_res_sum = 0
    dq_len = 10

    # execution
    for x in range(MAX_EPOCH):
        sum_reward_mean = 0
        step_cnt = 0
        env.reset()
        while True:
            obs_list = []
            action_list = []
            red_fighter_action = []
            # get obs
            if step_cnt == 0:
                red_obs_dict, blue_obs_dict = env.get_obs()
            # get action
            # get blue action
            blue_detector_action, blue_fighter_action = blue_agent.get_action(blue_obs_dict, step_cnt)
            # get red action
            obs_got_ind = [False] * red_fighter_num
            for y in range(red_fighter_num):
                true_action = np.array([0, 1, 0, 0], dtype=np.int32)
                if red_obs_dict['fighter'][y]['alive']:
                    obs_got_ind[y] = True
                    tmp_img_obs = red_obs_dict['fighter'][y]['screen']
                    tmp_img_obs = tmp_img_obs.transpose(2, 0, 1)
                    tmp_info_obs = red_obs_dict['fighter'][y]['info']
                    tmp_action = fighter_model.choose_action(tmp_img_obs, tmp_info_obs)
                    obs_list.append({'screen': copy.deepcopy(tmp_img_obs), 'info': copy.deepcopy(tmp_info_obs)})
                    action_list.append(tmp_action)
                    # action formation
                    true_action[0] = int(360 / COURSE_NUM * int(tmp_action[0] / ATTACK_IND_NUM))
                    true_action[3] = int(tmp_action[0] % ATTACK_IND_NUM)
                red_fighter_action.append(true_action)
            red_fighter_action = np.array(red_fighter_action)
            # step
            env.step(red_detector_action, red_fighter_action, blue_detector_action, blue_fighter_action)
            # get reward
            red_detector_reward, red_fighter_reward, red_game_reward, blue_detector_reward, blue_fighter_reward, blue_game_reward = env.get_reward()
            detector_reward = red_detector_reward + red_game_reward
            fighter_reward = red_fighter_reward + red_game_reward
            sum_reward_mean += np.mean(fighter_reward)
            # save repaly
            red_obs_dict, blue_obs_dict = env.get_obs()
            for y in range(red_fighter_num):
                if obs_got_ind[y]:
                    tmp_img_obs = red_obs_dict['fighter'][y]['screen']
                    tmp_img_obs = tmp_img_obs.transpose(2, 0, 1)
                    tmp_info_obs = red_obs_dict['fighter'][y]['info']
                    fighter_model.store_transition(obs_list[y], action_list[y], fighter_reward[y],
                                                   {'screen': copy.deepcopy(tmp_img_obs), 'info': copy.deepcopy(tmp_info_obs)})

            # if done, perform a learn
            if env.get_done():
                # detector_model.learn()

                """记录最近几场的胜负情况"""
                cur_episode_res = red_game_reward // 200
                recent_episode_res.append(cur_episode_res)
                episode_res_sum += cur_episode_res
                # pop
                dq_left = 0
                if len(recent_episode_res) > dq_len:
                    dq_left = recent_episode_res.popleft()
                episode_res_sum -= dq_left
                tb_logger.add_scalar('recent_' + str(dq_len) + '_episode_win_rate', episode_res_sum / dq_len, x)

                fighter_model.learn()
                break
            # if not done learn when learn interval
            if (step_cnt > 0) and (step_cnt % LEARN_INTERVAL == 0):
                # detector_model.learn()
                fighter_model.learn()
            step_cnt += 1

        tb_logger.add_scalar('avg_step_reward', sum_reward_mean / step_cnt, x)

        if x % 50 == 0:
            logging.info('episode:' + str(x) + ', episode reward: ' + str(sum_reward_mean / step_cnt))
            logging.info('epsilon: ' + str(fighter_model.epsilon))

