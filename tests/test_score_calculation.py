"""
Unit Tests for Score Calculation
---------------------------------
Tests the weighted score calculation and grade band assignment.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ai_grader import calculate_overall_score


class TestCalculateOverallScore:
    """Tests for the calculate_overall_score() function."""

    def _make_grading_result(self, scores_and_names):
        """Helper to create a grading result dict for testing."""
        return {
            'criteria_results': [
                {'criterion_name': name, 'score': score}
                for name, score in scores_and_names
            ]
        }

    def _make_rubric(self, criteria_and_weights):
        """Helper to create a rubric dict for testing."""
        return {
            'criteria': [
                {
                    'name': name,
                    'weighting': weight,
                    'grade_bands': [
                        {'range': '80-100'}, {'range': '70-79'},
                        {'range': '60-69'}, {'range': '50-59'},
                        {'range': '40-49'}, {'range': '30-39'},
                        {'range': '0-29'}
                    ]
                }
                for name, weight in criteria_and_weights
            ]
        }

    def test_equal_weights(self):
        """With equal weights, overall should be the simple average."""
        grading = self._make_grading_result([
            ('Criterion A', 60),
            ('Criterion B', 80),
        ])
        rubric = self._make_rubric([
            ('Criterion A', 50),
            ('Criterion B', 50),
        ])

        result = calculate_overall_score(grading, rubric)
        # (60*50 + 80*50) / (50+50) = 70.0
        assert result['overall_score'] == 70.0

    def test_unequal_weights(self):
        """Higher-weighted criteria should have more impact on overall."""
        grading = self._make_grading_result([
            ('Criterion A', 40),
            ('Criterion B', 80),
        ])
        rubric = self._make_rubric([
            ('Criterion A', 75),  # High weight on the low score
            ('Criterion B', 25),
        ])

        result = calculate_overall_score(grading, rubric)
        # (40*75 + 80*25) / (75+25) = (3000+2000)/100 = 50.0
        assert result['overall_score'] == 50.0

    def test_all_same_scores(self):
        """If all criteria get the same score, overall should equal that score."""
        grading = self._make_grading_result([
            ('Criterion A', 65),
            ('Criterion B', 65),
            ('Criterion C', 65),
        ])
        rubric = self._make_rubric([
            ('Criterion A', 33.3),
            ('Criterion B', 33.3),
            ('Criterion C', 33.4),
        ])

        result = calculate_overall_score(grading, rubric)
        assert result['overall_score'] == 65.0

    def test_grade_band_80_plus(self):
        """Score of 85 should fall in 80-100 band."""
        grading = self._make_grading_result([('Criterion A', 85)])
        rubric = self._make_rubric([('Criterion A', 100)])

        result = calculate_overall_score(grading, rubric)
        assert result['overall_grade_band'] == '80-100'

    def test_grade_band_70s(self):
        """Score of 74 should fall in 70-79 band."""
        grading = self._make_grading_result([('Criterion A', 74)])
        rubric = self._make_rubric([('Criterion A', 100)])

        result = calculate_overall_score(grading, rubric)
        assert result['overall_grade_band'] == '70-79'

    def test_grade_band_fail(self):
        """Score of 25 should fall in 0-29 band."""
        grading = self._make_grading_result([('Criterion A', 25)])
        rubric = self._make_rubric([('Criterion A', 100)])

        result = calculate_overall_score(grading, rubric)
        assert result['overall_grade_band'] == '0-29'

    def test_fuzzy_name_matching(self):
        """Should match criterion names even with slight differences."""
        grading = self._make_grading_result([
            ('Critical review of literature', 70),
        ])
        rubric = self._make_rubric([
            ('Critical review of relevant literature', 100),
        ])

        result = calculate_overall_score(grading, rubric)
        # Should match and use the rubric weight, not the default
        assert result['criteria_results'][0]['weighting'] == 100

    def test_zero_scores(self):
        """Should handle zero scores without crashing."""
        grading = self._make_grading_result([
            ('Criterion A', 0),
            ('Criterion B', 0),
        ])
        rubric = self._make_rubric([
            ('Criterion A', 50),
            ('Criterion B', 50),
        ])

        result = calculate_overall_score(grading, rubric)
        assert result['overall_score'] == 0


class TestWeightingCalculation:
    """Tests for how weightings affect overall score."""

    def test_single_criterion(self):
        """Single criterion should just return its score."""
        grading = {
            'criteria_results': [
                {'criterion_name': 'Only Criterion', 'score': 72}
            ]
        }
        rubric = {
            'criteria': [
                {
                    'name': 'Only Criterion',
                    'weighting': 100,
                    'grade_bands': [{'range': '70-79'}]
                }
            ]
        }

        result = calculate_overall_score(grading, rubric)
        assert result['overall_score'] == 72.0