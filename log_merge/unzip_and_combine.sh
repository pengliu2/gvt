current=`pwd`
folder=$1

cd ${folder}
for i in *.kernel.txt.gz
do
    gunzip ${i}
    extracted=${i%.gz}
done

cp log.kernel.txt dmesg.txt

i=0
while [ -e "backup.$i.log.kernel.txt" ]
do
    i=`expr $i + 1`
done 

while [ "$i" -gt "0" ]
do
    i=`expr $i - 1`
    ls -l backup.$i.log.kernel.txt
    cat backup.$i.log.kernel.txt >> dmesg.txt
done

cd ${current}