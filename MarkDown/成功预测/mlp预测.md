(E:\private_project\AI_application\ai_application_conda) E:\private_project\AI_application\Test_kraft_connect\Fix_File>python train_conbine.py
数据集大小: 575061
特征维度: 29
类别分布:
target
0    558223
1     16838
Name: count, dtype: int64

开始训练...
准确率: 0.9998

准确率: 0.9998

分类报告:
              precision    recall  f1-score   support

     Success       1.00      1.00      1.00    111645
        Fail       1.00      1.00      1.00      3368

    accuracy                           1.00    115013
   macro avg       1.00      1.00      1.00    115013
weighted avg       1.00      1.00      1.00    115013

混淆矩阵:
[[111635     10]
 [    12   3356]]

✅ 模型已保存为 block_anomaly_model.pkl
✅ 标准化器已保存为 scaler.pkl

特征重要性（基于第一层权重）:
   feature  importance
22     E23    0.315838
20     E21    0.264724
2       E3    0.217942
3       E4    0.205158
5       E6    0.147660
19     E20    0.145709
17     E18    0.132304
25     E26    0.126095
24     E25    0.125849
15     E16    0.122257

(E:\private_project\AI_application\ai_application_conda) E:\private_project\AI_application\Test_kraft_connect\Fix_File>python predict.py
发现 16839 个异常 BlockId
                     block_id  anomaly_prob
73   blk_-3677287108349736219      0.994148
104  blk_-5510234811525269820      1.000000
115  blk_-5702408115323102212      1.000000
187   blk_5241230347415537486      1.000000
211   blk_3928660122009128821      1.000000
247   blk_1304146096147655717      1.000000
253  blk_-6657994559993667391      1.000000
321   blk_7915586591795168841      1.000000
350   blk_7437462110814705943      1.000000
388   blk_8168970971430245965      1.000000