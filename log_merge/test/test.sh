#!/bin/sh
test_root=${PWD}
################################################################################
# Test merging multiple files"
################################################################################
cd sanity
python ../../src/merge.py -t 5 *.txt abc> test.log
diff -w -q test.log expected.log
if [ $? -ne 0 ]; then
    echo "============================="
    echo "Failed: merging multiple files"
    echo "============================="
    cd ${test_root}
    exit 1
fi

echo "============================="
echo "Succeeded!"
echo "============================="

rm -f test.log
cd ${test_root}

################################################################################
# Test robust 1
################################################################################
cd robust
python ../../src/merge.py -t 5 *.txt > test.log
diff -q -w test.log expected.log
if [ $? -ne 0 ]; then
    echo "============================="
    echo "Failed: robust"
    echo "============================="
    cd ${test_root}
    exit 1
fi

echo "============================="
echo "Succeeded!"
echo "============================="

rm -f test.log
cd ${test_root}

################################################################################
# Test different timezone 1
################################################################################
cd timezone
python ../../src/merge.py -t -5.5 main.txt kernel.txt > test.log
diff -q -w test.log tz_expected.log
if [ $? -ne 0 ]; then
    echo "============================="
    echo "Failed: different timezone"
    echo "============================="
    cd ${test_root}
    exit 1
fi

echo "============================="
echo "Succeeded!"
echo "============================="

rm -f test.log
cd ${test_root}

################################################################################
# Test different timezone 2
################################################################################
cd timezone
python ../../src/merge.py -t -5.5 main.txt kernel.txt > test.log
diff -q -w test.log tz_expected.log
if [ $? -ne 0 ]; then
    echo "============================="
    echo "Failed: different timezone"
    echo "============================="
    cd ${test_root}
    exit 1
fi

echo "============================="
echo "Succeeded!"
echo "============================="

rm -f test.log
cd ${test_root}

################################################################################
# Test bugreport 1
################################################################################
cd bugreport
python ../../src/bugreport.py bugreport1.txt --tz 5 2>test.log
diff -q -w test.log bugreport1_expected.txt
if [ $? -ne 0 ]; then
    echo "============================="
    echo "Failed: bugreport1"
    echo "============================="
    cd ${test_root}
    exit 1
fi

echo "============================="
echo "Succeeded!"
echo "============================="

rm -f test.log
cd ${test_root}

################################################################################
# Test bugreport 2
################################################################################
cd bugreport
python ../../src/bugreport.py bugreport2.txt --tz 5 > test.log
diff -q test.log bugreport2_expected.txt
if [ $? -ne 0 ]; then
    echo "============================="
    echo "Failed: bugreport2"
    echo "============================="
    cd ${test_root}
    exit 1
fi

echo "============================="
echo "Succeeded!"
echo "============================="

rm -f test.log
cd ${test_root}

################################################################################
# Test bugreport 3
################################################################################
cd bugreport
python ../../src/bugreport.py bugreport3.txt --tz 5 > test.log
diff -q test.log bugreport3_expected.txt
if [ $? -ne 0 ]; then
    echo "============================="
    echo "Failed: bugreport3"
    echo "============================="
    cd ${test_root}
    exit 1
fi

echo "============================="
echo "Succeeded!"
echo "============================="

rm -f test.log
cd ${test_root}

################################################################################
# Test bugreport 4
################################################################################
cd bugreport
python ../../src/bugreport.py bugreport4.txt --tz 5 > test.log
diff -q test.log bugreport4_expected.txt
if [ $? -ne 0 ]; then
    echo "============================="
    echo "Failed: bugreport4"
    echo "============================="
    cd ${test_root}
    exit 1
fi

echo "============================="
echo "Succeeded!"
echo "============================="

rm -f test.log
cd ${test_root}

cd bugreport

################################################################################
# Test bugreport 5
################################################################################
python ../../src/bugreport.py bugreport5.txt --tz 5 > test.log
diff -q test.log bugreport5_expected.txt
if [ $? -ne 0 ]; then
    echo "============================="
    echo "Failed: bugreport5"
    echo "============================="
    cd ${test_root}
    exit 1
fi

echo "============================="
echo "Succeeded!"
echo "============================="

rm -f test.log
cd ${test_root}

