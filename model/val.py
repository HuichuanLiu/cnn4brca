# Written by: Erick Cobos T. (a01184587@itesm.mx)
# Date: April 2016
""" Calculate IOU measure for different thresholds (for cross-validation)

	We use linearly spaced probabilities in the range between the smallest and 
	largest possible predicted probability (as estimated by the predictions on 
	a random example). Thresholds are the logits corresponding to these
	probabilities.
	
	Example:
		$ python3 val.py
		$ python3 val.py | tee eval
"""

import tensorflow as tf
import model
import csv
import scipy.misc
import numpy as np

checkpoint_dir = "checkpoint"
csv_path = "val/val.csv"
data_dir = "val/"
number_of_thresholds = 20

def post(logits, label, threshold):
	"""Creates segmentation assigning everything over the threshold a value of 
	255, anythig equals to background in label as 0 and anythign else 127. 
	
	Using the label may seem like cheating but the background part of the label 
	was generated by thresholding the original image to zero, so it is as if i
	did that here. Just that it is more cumbersome. Not that important either as
	I calculate IOU for massses and not for backgorund or breats tissue."""
	thresholded = np.ones(logits.shape, dtype='uint8') * 127
	thresholded[logits >= threshold] = 255
	thresholded[label == 0] = 0
	return thresholded
	
def metrics(segmentation, label):
	"""Returns an array with different metrics for the given image and label."""
	epsilon = 1e-7 # To avoid division by zero
	
	# Confusion matrix (only over breast area)
	true_positive = np.sum(np.logical_and(segmentation == 255, label == 255))
	false_positive = np.sum(np.logical_and(segmentation == 255, label != 255))
	true_negative = np.sum(np.logical_and(segmentation == 127, label == 127))
	false_negative = np.sum(np.logical_and(segmentation == 127, label != 127))
	
	# Evaluation metrics
	accuracy = (true_positive + true_negative) / (true_positive + true_negative 
									+ false_positive + false_negative + epsilon)
	sensitivity = true_positive / (true_positive + false_negative + epsilon)
	specificity = true_negative / (false_positive + true_negative + epsilon)
	precision = true_positive / (true_positive + false_positive + epsilon)
	recall = sensitivity
	iou = true_positive / (true_positive + false_positive + false_negative + 
						   epsilon)
	f1 = (2 * precision * recall) / (precision + recall + epsilon)
	g_mean = np.sqrt(sensitivity * specificity)
		
	metrics = [iou, f1, g_mean, accuracy, sensitivity, specificity, precision,
			   recall]

	return np.array(metrics)
	
def main():
	""" Loads network, reads image and returns mean metrics."""
	# Read csv file
	with open(csv_path) as f:
		lines = f.read().splitlines()
		
	# Image as placeholder.
	image = tf.placeholder(tf.float32, name='image')
	expanded = tf.expand_dims(image, 2)
	whitened = tf.image.per_image_whitening(expanded)
	
	# Define the model
	prediction = model.model(whitened, drop=tf.constant(False))
		
	# Get a saver
	saver = tf.train.Saver()

	# Launch the graph
	with tf.Session() as sess:
		# Restore variables
		checkpoint_path = tf.train.latest_checkpoint(checkpoint_dir)
		saver.restore(sess, checkpoint_path)
		model.log("Variables restored from:", checkpoint_path)
		
		# Get random thresholds (with probs in 10^unif(-3, 0) range)
		#probs = 10 ** np.random.uniform(-3, 0, number_of_thresholds) 
		#thresholds = np.log(probs) - np.log(1 - probs) # prob2logit
		
		# Get random thresholds (range estimated from a random example)
		rand_index = np.random.randint(len(lines))
		rand_line = lines[rand_index]
		for row in csv.reader([rand_line]): 
			# Read image
			image_path = data_dir + row[0]
			im = scipy.misc.imread(image_path)
		
			# Get prediction
			logits = prediction.eval({image: im})
			
			# Minimum and maximum predicted probability
			min_prob = 1/ (1 + np.exp(-logits.min()))
			max_prob = 1/ (1 + np.exp(-logits.max()))
			
			# Get thresholds in (min_prob, max_prob) range
			probs = np.linspace(min_prob, max_prob, number_of_thresholds)
			thresholds = np.log(probs) - np.log(1 - probs) #prob2logit
		
		# Validate each threshold
		for i in range(number_of_thresholds):
			print("Threshold {}: {} ({})".format(i, thresholds[i], probs[i]))
			
			# Reset reader and metric_accum
			csv_reader = csv.reader(lines)
			metric_accum = np.zeros(8)
			
			# For every example
			for row in csv_reader:
				# Read paths
				image_path = data_dir + row[0]
				label_path = data_dir + row[1]

				# Read image and label
				im = scipy.misc.imread(image_path)
				label = scipy.misc.imread(label_path)
			
				# Get prediction
				logits = prediction.eval({image: im})
			
				# Post-process prediction
				segmentation = post(logits, label, thresholds[i])
				
				# Calculate iou				
				metric_accum += metrics(segmentation, label)
			
			# Calculate mean iou
			number_of_examples = csv_reader.line_num
			mean_metrics = metric_accum/number_of_examples
			
			# Report metrics
			metric_names = ['IOU', 'F1-score', 'G-mean', 'Accuracy',
						   'Sensitivity', 'Specificity', 'Precision', 'Recall']
			for name, metric in zip(metric_names, mean_metrics):
				print("{}: {}".format(name, metric))
			print('')
				
		# Logistic loss (same for any threshold)
		label = tf.placeholder(tf.uint8, name='label')
		loss = model.logistic_loss(prediction, label)
		
		csv_reader = csv.reader(lines)
		loss_accum = 0
		for row in csv_reader:
			im = scipy.misc.imread(data_dir + row[0])
			lbl = scipy.misc.imread(data_dir + row[1])
			
			loss_accum += loss.eval({image:im, label:lbl})
			
		print("Logistic loss: ", loss_accum/csv_reader.line_num)
				
	return metrics, metric_names,
	
if __name__ == "__main__":
	main()
