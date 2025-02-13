#!/bin/bash
# これが一番いい感じだから、これをベースラインとする


path="./data"

python src/sn_providing/spotting_module.py.py --path $path --mean_silence_sec 5.58 --ignore_under_1sec

<< COMMENTOUT
test 集合での結果
diff_average: 2.9113
label_accuracy: 0.6925
confusion matrix: [
 [8262 1856]
 [1999  420]]
label_f1: 0.810
COMMENTOUT

echo "timing_algo: lognorm"
python src/sn_providing/spotting_module.py.py --path $path --timing_algo lognorm --ignore_under_1sec --lognorm_params '{"shape": 1.4902, "loc": 1.0, "scale": 1.9815}'
# diff_average: 5.4240

echo "timing_algo: gamma"
python src/sn_providing/spotting_module.py.py --path $path --timing_algo gamma --ignore_under_1sec --gamma_params '{"shape": 0.7183, "loc": 1.0, "scale": 6.3800}'
# diff_average: 3.8224

echo "timing_algo: expon"
python src/sn_providing/spotting_module.py.py --path $path --timing_algo expon --ignore_under_1sec --expon_params '{"loc": 1.0, "scale": 4.5825}'
# diff_average: 3.5467