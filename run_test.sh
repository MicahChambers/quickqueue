#!/bin/bash
source ~/.bashrc
set -x
branch=$1
outdir=$2
comparedir=$3
clean=$4

which python
cd ~/cruise/
git reset --hard
git fetch
git checkout $1
git pull || true


cd ros

if [[ "$clean" != "True" ]]; then
    catkin clean --all -y || true
fi
catkin build --no-status --summarize --no-notify -DCRUISE_ENABLE_ASSERTIONS=ON
source ~/.bashrc

for xx in ~/cruise/ros/src/perception_testing/testsuites/{full,smoke,staging}/*.yaml; do
    echo '----------------------------------------------------------'
    echo '----------------------------------------------------------'
    echo '----------------------------------------------------------'
    echo $xx
    rosrun perception_testing perc.py -t $xx -d $2/${xx%.yaml}/
done

if [[ $comparedir == "" ]]; then
    rosrun perception_testing multitest_stats  --input-dirs $outdir/*  -o $outdir/results.md
else
    rosrun perception_testing multitest_stats  --input-dirs $outdir/* --compare-dir $comparedir/* -o $outdir/results.md
fi

