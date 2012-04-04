current=`pwd`
zipped_file=$1.txt.gz
extracted_file=log.$1.txt
output=$1.txt
folder=$2

cd ${folder}
for i in *.${zipped_file}
do
    gunzip ${i}
done

rm -f $output

i=0
while [ -e "backup.$i.${extracted_file}" ]
do
    i=`expr $i + 1`
done 

while [ "$i" -gt "0" ]
do
    i=`expr $i - 1`
    ls -l backup.$i.${extracted_file}
    cat backup.$i.${extracted_file} >> $output
done

cat ${extracted_file} >> $output

cd ${current}
