# models/xgboost.py
import xgboost as xgb

class XGBoost:
    def __init__(self, num_classes,num_round):
        self.num_classes = num_classes
        self.num_round = num_round
        self.model = None

    def train(self, X, y):
        params = {
            'objective': 'multi:softmax',
            'num_class': self.num_classes,
            'tree_method': 'hist',
            'device' : 'cuda',  # 使用 GPU 加速
            'max_depth': 6,
            'eta': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'eval_metric': 'mlogloss'
        }
        dtrain = xgb.DMatrix(X, label=y)
        self.model = xgb.train(params, dtrain, num_boost_round=self.num_round)
        print("XGBoost 训练完成!")

    def predict(self, X):
        if self.model is None:
            raise ValueError("模型未训练，请先调用 train 方法。")
        dtest = xgb.DMatrix(X)
        return self.model.predict(dtest).astype(int)