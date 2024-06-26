python training/training_env.py \
  --num_env 1 \
  --num_eval_envs 1 \
  --tot_step 50 \
  --env balancing \
  --task_name throwing_RL \
  --Kb 100.0 \
  --mu 5.0 \
  --load_dir ../data/throwing_state \
  --reward_name compute_reward_throwing_RL \
  --model SAC