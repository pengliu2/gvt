current=`pwd`
zipped_file=$3.txt.gz
extracted_file=log.$3.txt
output=$3.txt
folder=$1
prefix=$2

cd ${folder}
for i in *.${zipped_file}
do
    gunzip ${i}
done

rm -f $output

i=0
while [ -e "${prefix}_backup.$i.${extracted_file}" ]
do
    i=`expr $i + 1`
done 

while [ "$i" -gt "0" ]
do
    i=`expr $i - 1`
    ls -l ${prefix}_backup.$i.${extracted_file}
    cat ${prefix}_backup.$i.${extracted_file} >> $output
done

cat ${prefix}_${extracted_file} >> $output

cd ${current}
