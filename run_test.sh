#!/bin/bash
source ~/.bashrc
set -x
branch=$1
outdir=$2
comparedir=$3

which python
cd ~/cruise/
git reset --hard
git fetch
git checkout $1
git pull || true


cd ros
catkin clean --all -y || true
catkin build --no-status --summarize --no-notify -DCRUISE_ENABLE_ASSERTIONS=ON
source ~/.bashrc

#for xx in ~/cruise/ros/src/regression_testing/testsuites/{full,smoke,staging}/*.yaml; do 
for xx in ~/cruise/ros/src/regression_testing/testsuites/smoke/general-00.yaml; do 
echo '----------------------------------------------------------'
echo '----------------------------------------------------------'
echo '----------------------------------------------------------'
	echo $xx
	rosrun regression_testing perc  -t $xx -d $2/${xx%.yaml}/
done

if [[ $comparedir == "" ]]; then 
	sleep 30
	echo rosrun regression_testing multitest_stats  --input-dirs $outdir/*  -o $outdir/results.md
else
	sleep 30
	echo rosrun regression_testing multitest_stats  --input-dirs $outdir/* --compare-dir $comparedir/* -o $outdir/results.md
fi

