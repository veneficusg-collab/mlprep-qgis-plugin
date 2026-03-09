import os
import json
from typing import Optional
from tensorflow.keras.callbacks import CSVLogger
from sys import setdlopenflags
from sklearn.metrics import confusion_matrix
from tensorflow import keras
from tensorflow.keras.layers import *
import tensorflow as tf
import seaborn as sns
from tensorflow.keras import layers, optimizers, losses, metrics, Model, Input
from sklearn.model_selection import KFold, StratifiedKFold
from keras_tuner import RandomSearch
import numpy as np
import sklearn
from matplotlib import pyplot as plt
from tensorflow import keras
from scikeras.wrappers import KerasClassifier
from tensorflow.python.data.ops.dataset_ops import dataset_autograph
from GallenModel_v1 import (
    DisplacementLayer,
    NewmarkActivation,
    CohesionLayer,
    InternalFrictionLayer,
)
# from GallenModel_v1 import FosLayer

# numeric_cols = [
#     "BD_mean",
#     "BD_std",
#     "Clay_mean",
#     "Clay_std",
#     "Sand_mean",
#     "Sand_std",
#     "Silt_mean",
#     "Silt_std",
#     "Est_mean",
#     "Est_std",
#     "Nrt_mean",
#     "Nrt_std",
#     "blk-unit_mean",
#     "blk-unit_stdev",
#     "wtr-cont_mean",
#     "wtr-cont_stdev",
#     # "HorCurv_mean",
#     # "HorCurv_std",
#     # "VertCurv_mean",
#     # "VertCurv_std",
#     "Slope_mean",
#     "Slope_std",
#     "PGA_mean",
#     "PGA_std",
#     "NDVI_mean",
#     "NDVI_std",
#     "Prc_mean",
#     "Prc_std",
# ]  # features that are fed into the model during training
numeric_cols = ['BD_mean','Clay_mean','Sand_mean','Silt_mean','Est_mean','Nrt_mean','HorCurv_mean','VertCurv_mean', 'Slope_mean', 'PGA_mean',
     'NDVI_mean', 'Prc_mean']
numeric_cols = [
    "Clay_mean",
    "Sand_mean",
    "Silt_mean",
    "NDVI_mean",
    "Est_mean",
    "Nrt_mean",
    "HorCurv_mean",
    "VertCurv_mean",
    "Slope_mean",
    "Elev_mean",
    "SoilThc_mean",
    "DistFlt_min",
    "LULC_majority",
    "TWI_mean",
    "Prc_mean",
    "Distrv_min",
    "distrd_min",
    "Soil Type",
    "BUK_mean",
]
# numeric_cols = [
#     "Est_m",
#     "Nrt_m",
#     "HC_m",
#     "VC_m",
#     "Slp_m",
#     "Prc_m",
#     "NDVI_m",
#     "PGA_Usgs",
#     "Sand_m",
#     "Silt_m",
#     "Clay_m",
#     "Bdod_m",
# ]  # numeric cols of nepal


class LandslideV2:
    def __init__(
        self, activation, optimizer, leaky_alpha: Optional[float] = None
    ) -> None:
        self.depth = 8
        self.activation = activation
        self.optimizer = optimizer
        self.leaky_alpha = leaky_alpha

    def get_multi_classification_model_no_pga(self, all_inputs, pga_input, encoded_features):
        units = [32, 64, 8, 64, 32, 8, 32, 8]
        all_features = tf.keras.layers.concatenate(encoded_features)
        features_only = all_features

        slope = all_inputs[numeric_cols.index("Slope_mean")]
        bulk_density = all_inputs[numeric_cols.index("BUK_mean")]

        x = layers.Dense(
            units=64,
            name="Sus_0",
            kernel_initializer="random_normal",
            bias_initializer="random_normal",
        )(features_only)

        for i in range(1, self.depth + 1):
            x = layers.Dense(
                units=units[i - 1],
                name=f"Sus_{i}",
                kernel_initializer="random_normal",
                bias_initializer="random_normal",
            )(x)
            x = layers.BatchNormalization()(x)
            if self.activation == "prelu":
                x = layers.PReLU()(x)
            elif self.activation == "relu":
                x = layers.ReLU()(x)
            elif self.activation == "leaky":
                if self.leaky_alpha == None:
                    raise Exception("Missing leaky ReLU alpha value")
                x = layers.LeakyReLU(negative_slope=self.leaky_alpha)(x)
            else:
                x = layers.ReLU()(x)  # defaults to ReLU activation if none of the above

        x = layers.Dense(units=2, name="geotechnical_param")(x)
        if self.activation == "prelu":
            x = layers.PReLU()(x)
        elif self.activation == "relu":
            x = layers.ReLU()(x)
        elif self.activation == "leaky":
            if self.leaky_alpha == None:
                raise Exception("Missing leaky ReLU alpha value")
            x = layers.LeakyReLU(negative_slope=self.leaky_alpha)(x)
        else:
            print("default activation")
            x = layers.ReLU()(x)  # defaults to ReLU activation if none of the above

        coh = CohesionLayer()(x)
        ifi = InternalFrictionLayer()(x)

        # NOTE::not used currently the clipping thingy
        # coh = layers.Lambda(lambda x: tf.clip_by_value(x, 5.0, 40.0))(coh)
        # ifi = layers.Lambda(lambda x: tf.clip_by_value(x, 0.0, 60.0))(ifi)

        ds, safety_factor = DisplacementLayer()([coh, ifi, slope, pga_input, bulk_density])

        if self.activation == "prelu":
            ds = layers.PReLU()(ds)
        elif self.activation == "relu":
            ds = layers.ReLU()(ds)
        elif self.activation == "leaky":
            if self.leaky_alpha == None:
                raise Exception("Missing leaky ReLU alpha value")
            ds = layers.LeakyReLU(negative_slope=self.leaky_alpha)(ds)
        else:
            print("default")
            ds = layers.ReLU()(ds)  # defaults to ReLU activation if none of the above

        K = 4
        sus = layers.Dense(units=K, activation='softmax', name="susceptibility")
        # sus = layers.Activation('sigmoid')(ds)

        self.model = Model(inputs= all_inputs + [pga_input], outputs=sus)


    def get_classification_model_no_pga(self, all_inputs, pga_input, encoded_features):

        units = [32, 64, 8, 64, 32, 8, 32, 8]
        all_features = tf.keras.layers.concatenate(encoded_features)
        features_only = all_features

        slope = all_inputs[numeric_cols.index("Slope_mean")]
        bulk_density = all_inputs[numeric_cols.index("BUK_mean")]

        x = layers.Dense(
            units=64,
            name="Sus_0",
            kernel_initializer="random_normal",
            bias_initializer="random_normal",
        )(features_only)

        for i in range(1, self.depth + 1):
            x = layers.Dense(
                units=units[i - 1],
                name=f"Sus_{i}",
                kernel_initializer="random_normal",
                bias_initializer="random_normal",
            )(x)
            x = layers.BatchNormalization()(x)
            if self.activation == "prelu":
                x = layers.PReLU()(x)
            elif self.activation == "relu":
                x = layers.ReLU()(x)
            elif self.activation == "leaky":
                if self.leaky_alpha == None:
                    raise Exception("Missing leaky ReLU alpha value")
                x = layers.LeakyReLU(negative_slope=self.leaky_alpha)(x)
            else:
                x = layers.ReLU()(x)  # defaults to ReLU activation if none of the above

        x = layers.Dense(units=2, name="geotechnical_param")(x)
        if self.activation == "prelu":
            x = layers.PReLU()(x)
        elif self.activation == "relu":
            x = layers.ReLU()(x)
        elif self.activation == "leaky":
            if self.leaky_alpha == None:
                raise Exception("Missing leaky ReLU alpha value")
            x = layers.LeakyReLU(negative_slope=self.leaky_alpha)(x)
        else:
            print("default activation")
            x = layers.ReLU()(x)  # defaults to ReLU activation if none of the above

        coh = CohesionLayer()(x)
        ifi = InternalFrictionLayer()(x)

        # NOTE::not used currently the clipping thingy
        # coh = layers.Lambda(lambda x: tf.clip_by_value(x, 5.0, 40.0))(coh)
        # ifi = layers.Lambda(lambda x: tf.clip_by_value(x, 0.0, 60.0))(ifi)

        ds = DisplacementLayer()([coh, ifi, slope, pga_input, bulk_density])
        # safety_factor = FosLayer()(safety_factor)
        if self.activation == "prelu":
            ds = layers.PReLU()(ds)
        elif self.activation == "relu":
            ds = layers.ReLU()(ds)
        elif self.activation == "leaky":
            if self.leaky_alpha == None:
                raise Exception("Missing leaky ReLU alpha value")
            ds = layers.LeakyReLU(negative_slope=self.leaky_alpha)(ds)
        else:
            print("default")
            ds = layers.ReLU()(ds)  # defaults to ReLU activation if none of the above

        sus = NewmarkActivation(2.0)(ds)
        # sus = layers.Activation('sigmoid')(ds)

        self.model = Model(inputs= all_inputs + [pga_input], outputs=sus)


    def get_classification_model(self, all_inputs, encoded_features):

        units = [32, 64, 8, 64, 32, 8, 32, 8]
        all_features = tf.keras.layers.concatenate(encoded_features)
        features_only = all_features
        slope = all_inputs[numeric_cols.index("Slope_mean")]
        pga = all_inputs[numeric_cols.index("PGA1_max")]
        bulk_density = all_inputs[numeric_cols.index("BUK_mean")]

        x = layers.Dense(
            units=64,
            name="Sus_0",
            kernel_initializer="random_normal",
            bias_initializer="random_normal",
        )(features_only)

        for i in range(1, self.depth + 1):
            x = layers.Dense(
                units=units[i - 1],
                name=f"Sus_{i}",
                kernel_initializer="random_normal",
                bias_initializer="random_normal",
            )(x)
            x = layers.BatchNormalization()(x)
            if self.activation == "prelu":
                x = layers.PReLU()(x)
            elif self.activation == "relu":
                x = layers.ReLU()(x)
            elif self.activation == "leaky":
                if self.leaky_alpha == None:
                    raise Exception("Missing leaky ReLU alpha value")
                x = layers.LeakyReLU(negative_slope=self.leaky_alpha)(x)
            else:
                x = layers.ReLU()(x)  # defaults to ReLU activation if none of the above

        x = layers.Dense(units=2, name="geotechnical_param")(x)
        if self.activation == "prelu":
            x = layers.PReLU()(x)
        elif self.activation == "relu":
            x = layers.ReLU()(x)
        elif self.activation == "leaky":
            if self.leaky_alpha == None:
                raise Exception("Missing leaky ReLU alpha value")
            x = layers.LeakyReLU(negative_slope=self.leaky_alpha)(x)
        else:
            print("default activation")
            x = layers.ReLU()(x)  # defaults to ReLU activation if none of the above

        coh = CohesionLayer()(x)
        ifi = InternalFrictionLayer()(x)

        # NOTE::not used currently the clipping thingy
        # coh = layers.Lambda(lambda x: tf.clip_by_value(x, 5.0, 40.0))(coh)
        # ifi = layers.Lambda(lambda x: tf.clip_by_value(x, 0.0, 60.0))(ifi)

        ds = DisplacementLayer()([coh, ifi, slope, pga, bulk_density])

        if self.activation == "prelu":
            ds = layers.PReLU()(ds)
        elif self.activation == "relu":
            ds = layers.ReLU()(ds)
        elif self.activation == "leaky":
            if self.leaky_alpha == None:
                raise Exception("Missing leaky ReLU alpha value")
            ds = layers.LeakyReLU(negative_slope=self.leaky_alpha)(ds)
        else:
            print("default")
            ds = layers.ReLU()(ds)  # defaults to ReLU activation if none of the above

        # sus = NewmarkActivation(2.0)(ds)
        sus = layers.Activation('sigmoid')(sus)

        self.model = Model(inputs=all_inputs, outputs=sus)

    # NOTE::No momentum yet
    # def get_optimizer(self, lr=2.9064680405339487e-05):
    def get_optimizer(self, lr=1e-05):
        if self.optimizer == "adam":
            self.optimizer_instance = optimizers.Adam(learning_rate=lr)
        elif self.optimizer == "rmsprop":
            self.optimizer_instance = optimizers.RMSprop(learning_rate=lr)
        if self.optimizer == "sgd":
            self.optimizer_instance = optimizers.SGD(learning_rate=lr)

    def compile_model(self):
        self.model.compile(
            optimizer=self.optimizer_instance,
            loss=losses.BinaryCrossentropy(),
            metrics=[
                metrics.BinaryIoU(target_class_ids=[0, 1], threshold=0.5),
                metrics.AUC(),
                "accuracy",
            ],
        )

    def compile_multiclass_model(self):
        self.model.compile(
            optimizer=self.optimizer_instance,
            loss=tf.keras.losses.SparseCategoricalCrossentropy(),
            metrics=[
                metrics.BinaryIoU(target_class_ids=[0, 1], threshold=0.5),
                metrics.AUC(),
                "accuracy",
            ],
        )
        

    def compile_model_dce(self):
        # dice_loss = tf.keras.losses.Dice()
        dce_loss = DiceCrossEntropyLoss()
        self.model.compile(
            optimizer=self.optimizer_instance,
            loss=dce_loss,
            metrics=[
                metrics.BinaryIoU(target_class_ids=[0, 1], threshold=0.5),
                metrics.AUC(),
                "accuracy",
            ],
        )

def plot_auc(
    y_true,
    y_preds,
    threshold,
    activation: Optional[str] = None,
    optimizer: Optional[str] = None,
):
    print(threshold)
    fpr, tpr, thresholds = sklearn.metrics.roc_curve(y_true, y_preds)
    auc = sklearn.metrics.auc(fpr, tpr)
    acc = round(sklearn.metrics.balanced_accuracy_score(y_true, y_preds > 0.5), 2)
    plt.plot(
        fpr,
        tpr,
        lw=1,
        alpha=0.3,
        label=f"(AUC={auc:.2f}, Acc={acc}) Activation: {activation} Optimizer: {optimizer}",
    )
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curves North Cotabato Dataset")
    plt.legend(loc="lower right")
    plt.grid(True)
    plt.tight_layout()
    plt.show()
    return


def plot_confusion_matrix(preds,test_y, threshold):
    print(threshold)
    y_pred_classes = (preds > 0.5).astype(
        "int32"
    )  # threshold for binary classification
    cm = confusion_matrix(test_y, y_pred_classes)
    plt.figure(figsize=(6, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title("Confusion Matrix")
    plt.show()

def dice(y_true, y_pred, smooth):
    y_true = tf.cast(y_true, tf.float32)
    y_pred = tf.cast(y_pred, tf.float32)

    y_true = tf.reshape(y_true, [-1])
    y_pred = tf.reshape(y_pred, [-1])

    intersection = tf.reduce_sum(y_true * y_pred)
    pred_sum = tf.reduce_sum(y_pred)
    true_sum = tf.reduce_sum(y_true)

    dice_value = (2.0 * intersection + smooth) / (pred_sum + true_sum + smooth)
    return 1 - dice_value


    
def weighted_bce( y_true, y_pred, a):
    y_true = tf.cast(y_true, tf.float32)
    y_pred = tf.clip_by_value(y_pred, 1e-7, 1 - 1e-7)

    first_term = (1 - a) * y_true * tf.math.log(y_pred)
    second_term = (a * (1 - y_true) * tf.math.log(1 - y_pred))
    loss = -(first_term + second_term)
    
    reduced_loss = tf.reduce_mean(loss)
    return reduced_loss

@tf.keras.utils.register_keras_serializable()
class DiceCrossEntropyLoss(tf.keras.losses.Loss):
    def __init__(self, a = 0.25, b = 0.5, smooth=1e-06, name="DiceCELoss", reduction='sum_over_batch_size', n_l = 1.0):
        super().__init__(name=name)
        self.a = a
        self.b = b
        self.smooth = smooth
    def call (self, y_true, y_pred):
        bce = weighted_bce(y_true, y_pred, self.a)
        dice_loss = dice(y_true, y_pred, self.smooth)
        return self.b * bce + (1 - self.b) * dice_loss
    
    def get_config(self):
        config = super().get_config()
        config.update({"name": self.name})
        return config
