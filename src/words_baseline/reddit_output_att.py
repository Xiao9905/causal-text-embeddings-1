from semi_parametric_estimation.att import att_estimates, psi_plugin, psi_q_only
from reddit.data_cleaning.reddit_posts import load_reddit_processed
from .helpers import filter_document_embeddings, make_index_mapping, assign_split
import numpy as np
import pandas as pd
import os
from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge
from sklearn.metrics import mean_squared_error as mse
import argparse
import sys
from scipy.special import logit
from scipy.sparse import load_npz

def get_log_outcomes(outcomes):
	#relu
	outcomes = np.array([max(0.0, out) + 1.0  for out in outcomes])
	return np.log(outcomes)

def predict_expected_outcomes(model, features):
	return model.predict(features)

def fit_conditional_expected_outcomes(outcomes, features):
	model = Ridge()
	model.fit(features, outcomes)
	predict = model.predict(features)
	if verbose:
		print("Training MSE:", mse(outcomes, predict))
	return model

def predict_treatment_probability(labels, features):
	model = LogisticRegression(solver='liblinear')
	model.fit(features, labels)
	if verbose:
		print("Training accuracy:", model.score(features, labels))
	treatment_probability = model.predict_proba(features)[:,1]
	return treatment_probability

def load_simulated_data():
	sim_df = pd.read_csv(simulation_file, delimiter='\t')
	sim_df = sim_df.rename(columns={'index':'post_index'})
	return sim_df

def load_term_counts(path='../dat/reddit/'):
	return load_npz(path + 'term_counts.npz').toarray()

def main():
	
	if not dat_dir:
		term_counts = load_term_counts()
	else:
		term_counts = load_term_counts(path=dat_dir)

	sim_df = load_simulated_data()
	treatment_labels = sim_df.treatment.values
	indices = sim_df.post_index.values
	all_words = term_counts[indices, :]

	treated_sim = sim_df[sim_df.treatment==1]
	untreated_sim = sim_df[sim_df.treatment==0]
	treated_indices = treated_sim.post_index.values
	untreated_indices = untreated_sim.post_index.values
	
	all_outcomes = sim_df.outcome.values
	outcomes_st_treated = treated_sim.outcome.values
	outcomes_st_not_treated = untreated_sim.outcome.values
	
	words_st_treated = term_counts[treated_indices,:]
	words_st_not_treated = term_counts[untreated_indices,:]

	treatment_probability = predict_treatment_probability(treatment_labels, all_words)
	model_outcome_st_treated = fit_conditional_expected_outcomes(outcomes_st_treated, words_st_treated)
	model_outcome_st_not_treated = fit_conditional_expected_outcomes(outcomes_st_not_treated, words_st_not_treated)

	expected_outcome_st_treated = predict_expected_outcomes(model_outcome_st_treated, all_words)
	expected_outcome_st_not_treated = predict_expected_outcomes(model_outcome_st_not_treated, all_words)

	q_hat = psi_q_only(expected_outcome_st_not_treated, expected_outcome_st_treated, 
			treatment_probability, treatment_labels, all_outcomes, truncate_level=0.03, prob_t=treatment_labels.mean())

	tmle = psi_plugin(expected_outcome_st_not_treated, expected_outcome_st_treated, 
			treatment_probability, treatment_labels, all_outcomes, truncate_level=0.03, prob_t=treatment_labels.mean())
	
	print("Q hat:", q_hat)
	print("TMLE:", tmle)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--dat-dir", action="store", default=None)
	parser.add_argument("--sim-dir", action="store", default='../dat/sim/reddit_subreddit_based/')
	parser.add_argument("--subs", action="store", default='13,6,8')
	parser.add_argument("--mode", action="store", default="simple")
	parser.add_argument("--params", action="store", default="1.0,1.0,1.0")
	parser.add_argument("--verbose", action='store_true')
	args = parser.parse_args()

	sim_dir = args.sim_dir
	dat_dir = args.dat_dir
	subs = None
	if args.subs != '':
		subs = [int(s) for s in args.subs.split(',')]
	verbose = args.verbose
	params = args.params.split(',')
	sim_setting = 'beta0' + params[0] + '.beta1' + params[1] + '.gamma' + params[2]
	subs_string = ', '.join(args.subs.split(','))
	mode = args.mode
	simulation_file = sim_dir + 'subreddits['+ subs_string + ']/mode' + mode + '/' + sim_setting + ".tsv"

	main()