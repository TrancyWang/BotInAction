import json
import os
import argparse
import random

import tensorflow as tf
from chapter10.dssm.data_helper import DnnDssmData
from model import DnnDssmModel
from chapter10.dssm.metrics import mean,accuracy

RATE = 0.2


class Trainer(object):
    def __init__(self, args):
        self.args = args
        with open(args.config_path, "r", encoding="utf8") as fr:
            self.config = json.load(fr)

        # self.builder = tf.saved_model.builder.SavedModelBuilder("../pb_model/weibo/bilstm/savedModel")
        # 加载数据集
        self.data_obj = self.load_data()
        queries = self.data_obj.gen_data(self.config["train_data"])
        print("vocab size: ", self.data_obj.vocab_size)
        self.train_queries, self.eval_queries = self.split_train_eval_data(queries, RATE)

        # 初始化模型对象
        self.model = self.create_model()

    @staticmethod
    def split_train_eval_data(queries, rate):
        """

        :param queries:
        :param rate:
        :return:
        """
        random.shuffle(queries)

        split_index = int(len(queries) * rate)
        train_queries = queries[split_index:]
        eval_queries = queries[:split_index]

        return train_queries, eval_queries

    def load_data(self):
        """
        创建数据对象
        :return:
        """
        # 生成训练集对象并生成训练数据
        data_obj = DnnDssmData(self.config)

        return data_obj

    def create_model(self):
        """
        根据config文件选择对应的模型，并初始化
        :return:
        """

        model = DnnDssmModel(config=self.config,
                             vocab_size=self.data_obj.vocab_size,
                             word_vectors=self.data_obj.word_vectors)

        return model

    def train(self):
        """
        训练模型
        :return:
        """
        gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.9, allow_growth=True)
        sess_config = tf.ConfigProto(log_device_placement=False, allow_soft_placement=True, gpu_options=gpu_options)
        with tf.Session(config=sess_config) as sess:
            # 初始化变量值
            sess.run(tf.global_variables_initializer())
            current_step = 0

            for epoch in range(self.config["epochs"]):
                print("----- Epoch {}/{} -----".format(epoch + 1, self.config["epochs"]))

                for batch in self.data_obj.next_batch(self.train_queries, self.config["batch_size"]):
                    loss, predictions = self.model.train(sess, batch, self.config["keep_prob"])

                    acc = accuracy(predictions)

                    print("train: step: {}, loss: {}, acc: {}".format(current_step, loss, acc))

                    current_step += 1
                    if current_step % self.config["checkpoint_every"] == 0:

                        eval_losses = []
                        eval_acc = []

                        for eval_batch in self.data_obj.next_batch(self.eval_queries, self.config["batch_size"]):
                            eval_loss, eval_predictions = self.model.eval(sess, eval_batch)
                            eval_losses.append(eval_loss)

                            acc = accuracy(eval_predictions)
                            eval_acc.append(acc)

                        print("\n")
                        print("eval: , loss: {}, acc: {}".format(mean(eval_losses), mean(eval_acc)))

                        print("\n")

                        if self.config["ckpt_model_path"]:
                            save_path = os.path.join(os.path.abspath(os.getcwd()),
                                                     self.config["ckpt_model_path"])
                            if not os.path.exists(save_path):
                                os.makedirs(save_path)
                            model_save_path = os.path.join(save_path, self.config["model_name"])
                            self.model.saver.save(sess, model_save_path, global_step=current_step)

            # inputs = {"inputs": tf.saved_model.utils.build_tensor_info(self.model.inputs),
            #           "keep_prob": tf.saved_model.utils.build_tensor_info(self.model.keep_prob)}
            #
            # outputs = {"predictions": tf.saved_model.utils.build_tensor_info(self.model.predictions)}
            #
            # # method_name决定了之后的url应该是predict还是classifier或者regress
            # prediction_signature = tf.saved_model.signature_def_utils.build_signature_def(inputs=inputs,
            #                                                                               outputs=outputs,
            #                                                                               method_name=tf.saved_model.signature_constants.PREDICT_METHOD_NAME)
            # legacy_init_op = tf.group(tf.tables_initializer(), name="legacy_init_op")
            # self.builder.add_meta_graph_and_variables(sess, [tf.saved_model.tag_constants.SERVING],
            #                                           signature_def_map={"classifier": prediction_signature},
            #                                           legacy_init_op=legacy_init_op)
            #
            # self.builder.save()


if __name__ == "__main__":
    # 读取用户在命令行输入的信息
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_path", help="config path of model")
    args = parser.parse_args()
    trainer = Trainer(args)
    trainer.train()
