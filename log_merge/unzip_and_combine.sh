current=`pwd`
if [ $# -eq "3" ]
then
    zipped_file=$3.txt.gz
    extracted_file=log.$3.txt
    output=$3.txt
    folder=$1
    prefix=$2_
else 
    if [ $# -eq "2" ]
    then
        zipped_file=$2.txt.gz
        extracted_file=log.$2.txt
        output=$2.txt
        folder=$1
        prefix=""
    fi
fi

cd ${folder}
for i in *.${zipped_file}
do
    gunzip ${i}
done

rm -f $output

i=0
while [ -e "${prefix}backup.$i.${extracted_file}" ]
do
    i=`expr $i + 1`
done 

while [ "$i" -gt "0" ]
do
    i=`expr $i - 1`
    ls -l ${prefix}backup.$i.${extracted_file}
    cat ${prefix}backup.$i.${extracted_file} >> $output
done

cat ${prefix}${extracted_file} >> $output

cd ${current}
