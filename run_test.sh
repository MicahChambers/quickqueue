#!/bin/bash
source ~/.bashrc
set -x
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
branch=$1
outdir=$DIR/$2
comparedir=$DIR/$3
clean=$4


echo 'cruise_PROGRESS: Checking out'
which python
cd ~/cruise/
git reset --hard
git fetch
git checkout $1
git pull || true


cd ros

echo 'cruise_PROGRESS: Building'
if [[ "$clean" != "True" ]]; then
    catkin clean --all -y || true
fi
catkin build --no-status --summarize --no-notify -DCRUISE_ENABLE_ASSERTIONS=ON
source ~/.bashrc

for xx in ~/cruise/ros/src/perception_testing/testsuites/{full,smoke,staging}/*.yaml; do
    echo $xx
    testname=`basename $xx`
    testname=${testname%.yaml}
    echo "cruise_PROGRESS: $testname"
    mkdir $outdir/$testname/
    rosrun perception_testing perc.py -t $xx -d $outdir/$testname/
done

echo "cruise_PROGRESS: Stats"
input_dirs=`find "$outdir" -name debug.segments.json | while read line; do dirname $line; done`
if [[ $comparedir == "" ]]; then
    rosrun perception_testing multitest_stats.py  --input-dirs $input_dirs \
        -o $outdir/results.md
else
    compare_dirs=`find "$comparedir" -name debug.segments.json | while read line; do dirname $line; done`
    if [[ $compare_dirs == "" ]]; then
        rosrun perception_testing multitest_stats.py  --input-dirs $input_dirs \
            -o $outdir/results.md
    else
        rosrun perception_testing multitest_stats.py  --input-dirs $input_dirs \
            --compare-dirs $compare_dirs -o $outdir/results.md
    fi
fi

echo "cruise_PROGRESS: Done"
