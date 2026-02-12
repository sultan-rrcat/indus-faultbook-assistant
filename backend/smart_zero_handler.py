import re
from typing import Tuple, Dict, Any
import pandas as pd
import config
import logging
import traceback

# --- Logging Setup ---
config.setup_logging()
logger = logging.getLogger(__name__)
logger.info("SmartZeroResultsHandler module loaded and logging initialized.")

class SmartZeroResultsHandler:
    """
    Handles zero-result scenarios by distinguishing between legitimate zeros
    and potential query issues (typos, wrong filters, etc.)
    """
    
    def __init__(self, nl2sql_obj, logger):
        self.nl2sql_obj = nl2sql_obj
        self.logger = logger
        self.logger.debug("SmartZeroResultsHandler initialized.")

    def analyze_zero_results(
        self, 
        user_query: str, 
        sql_query: str, 
        df_result: pd.DataFrame
    ) -> Dict[str, Any]:
        """Main entry point: analyze why query returned zero results."""
        self.logger.info("Analyzing zero results.")
        self.logger.debug(f"User query: {user_query}")
        self.logger.debug(f"SQL query: {sql_query}")
        self.logger.debug(f"Result DataFrame shape: {df_result.shape}")

        try:
            if self._is_count_query_with_zero(df_result):
                self.logger.info("Detected COUNT query with zero result.")
                return self._handle_count_zero(user_query, sql_query)
            
            self.logger.info("Detected non-COUNT query with zero results. Running diagnostics.")
            return self._diagnose_no_matches(user_query, sql_query)
        
        except Exception as e:
            self.logger.error(f"Error during zero-result analysis: {e}")
            self.logger.debug(traceback.format_exc())
            return {
                'is_legitimate_zero': False,
                'confidence': 0.0,
                'diagnostic_info': {'error': str(e)},
                'suggested_prompt': "An internal error occurred during analysis. Please try again."
            }

    def _is_count_query_with_zero(self, df_result: pd.DataFrame) -> bool:
        """Check if this is a COUNT(*) query that returned 0"""
        self.logger.debug("Checking if query is a COUNT query returning zero.")
        try:
            if len(df_result) == 1 and df_result.shape[1] == 1:
                col_name = df_result.columns[0].lower()
                value = df_result.iloc[0, 0]
                is_count = any(keyword in col_name for keyword in ['count', 'total', 'number'])
                self.logger.debug(f"Column: {col_name}, Value: {value}, is_count: {is_count}")
                return is_count and isinstance(value, (int, float)) and value == 0
            return False
        except Exception as e:
            self.logger.error(f"Error in _is_count_query_with_zero: {e}")
            self.logger.debug(traceback.format_exc())
            return False

    def _handle_count_zero(self, user_query: str, sql_query: str) -> Dict[str, Any]:
        """Handle COUNT queries that returned 0"""
        self.logger.info("Handling COUNT(*) zero result query.")
        has_suspicious_filters = self._check_suspicious_filters(sql_query, user_query)

        if has_suspicious_filters['suspicious']:
            self.logger.warning(f"Suspicious filters detected: {has_suspicious_filters['issues']}")
            confidence = 0.3
            diagnostic_info = {
                'reason': 'suspicious_filters',
                'details': has_suspicious_filters['issues']
            }
            suggested_prompt = self._generate_clarification_prompt(
                user_query, has_suspicious_filters['issues']
            )
        else:
            self.logger.info("No suspicious filters detected. Treating as likely legitimate zero.")
            confidence = 0.6
            diagnostic_info = {
                'reason': 'needs_verification',
                'details': 'Should verify with relaxed filters'
            }
            suggested_prompt = self._generate_verification_prompt(sql_query)
        
        self.logger.debug(f"Confidence: {confidence}, Diagnostic info: {diagnostic_info}")
        return {
            'is_legitimate_zero': confidence > 0.5,
            'confidence': confidence,
            'diagnostic_info': diagnostic_info,
            'suggested_prompt': suggested_prompt
        }

    def _diagnose_no_matches(self, user_query: str, sql_query: str) -> Dict[str, Any]:
        """Diagnose why a non-count query returned no matches"""
        self.logger.info("Diagnosing non-count zero-result query.")
        issues = []
        
        # entity_issues = self._check_entity_names(sql_query)
        # if entity_issues:
        #     self.logger.debug(f"Entity name issues detected: {entity_issues}")
        #     issues.extend(entity_issues)
        
        restrictive_filters = self._check_filter_restrictiveness(sql_query)
        if restrictive_filters:
            self.logger.debug(f"Restrictive filters detected: {restrictive_filters}")
            issues.extend(restrictive_filters)
        
        has_related_data = self._test_relaxed_query(sql_query)
        self.logger.debug(f"Related data exists: {has_related_data}")

        if issues or not has_related_data:
            confidence = 0.2
            suggested_prompt = self._generate_diagnostic_prompt(issues, has_related_data)
        else:
            confidence = 0.7
            suggested_prompt = config.LEGITIMATE_ZERO_PROMPT
        
        self.logger.info(f"Diagnosis completed with confidence {confidence}.")
        return {
            'is_legitimate_zero': confidence > 0.5,
            'confidence': confidence,
            'diagnostic_info': {
                'issues': issues,
                'has_related_data': has_related_data
            },
            'suggested_prompt': suggested_prompt
        }

    def _check_suspicious_filters(self, sql_query: str, user_query: str) -> Dict[str, Any]:
        """Check if WHERE clause has suspicious patterns"""
        self.logger.debug("Checking for suspicious filters in WHERE clause.")
        issues = []
        try:
            where_match = re.search(r'WHERE\s+(.+?)(?:GROUP BY|ORDER BY|$)', sql_query, re.IGNORECASE | re.DOTALL)
            if not where_match:
                self.logger.debug("No WHERE clause detected.")
                return {'suspicious': False, 'issues': []}
            
            where_clause = where_match.group(1)
            exact_matches = re.findall(r"=\s*'([^']+)'", where_clause)
            
            for match in exact_matches:
                if len(match) > 2 and match.lower() not in user_query.lower():
                    issues.append(f"Exact match on '{match}' (possible typo or mismatch)")
            
            if 'BETWEEN' in where_clause.upper() and 'AND' in where_clause.upper():
                issues.append("Very specific date range filter applied")
            
            self.logger.debug(f"Suspicious filter analysis result: {issues}")
            return {'suspicious': len(issues) > 0, 'issues': issues}

        except Exception as e:
            self.logger.error(f"Error checking suspicious filters: {e}")
            self.logger.debug(traceback.format_exc())
            return {'suspicious': False, 'issues': [str(e)]}

    def _find_similar_entities(self, entity: str, threshold: int = 2) -> list:
        """Stub for fuzzy entity lookup"""
        self.logger.debug(f"Searching for entities similar to '{entity}' (threshold={threshold}).")
        # Placeholder logic - to be replaced with actual fuzzy DB check
        return []

    def _check_filter_restrictiveness(self, sql_query: str) -> list:
        """Check if query filters are overly restrictive."""
        self.logger.debug("Checking query for overly restrictive filters.")
        issues = []
        and_count = sql_query.upper().count(' AND ')
        if and_count > 3:
            issues.append({
                'type': 'too_many_filters',
                'detail': f'{and_count} filters applied simultaneously'
            })
            self.logger.warning(f"Query has too many filters: {and_count}")
        return issues

    def _test_relaxed_query(self, sql_query: str) -> bool:
        """Run a relaxed query to check for related data."""
        self.logger.debug("Testing relaxed version of query.")
        try:
            base_query = re.sub(r'WHERE\s+.+?(?=GROUP BY|ORDER BY|LIMIT|$)', '', sql_query, flags=re.IGNORECASE | re.DOTALL)
            base_query = base_query.strip()
            if 'LIMIT' not in base_query.upper():
                base_query += ' LIMIT 1'
            
            self.logger.debug(f"Executing relaxed query: {base_query}")
            df = self.nl2sql_obj.execute_query(base_query)
            self.logger.debug(f"Relaxed query returned {len(df)} rows.")
            return len(df) > 0
        
        except Exception as e:
            self.logger.error(f"Error testing relaxed query: {e}")
            self.logger.debug(traceback.format_exc())
            return False

    def _generate_clarification_prompt(self, user_query: str, issues: list) -> str:
        """Generate prompt when user clarification is needed."""
        self.logger.debug("Generating clarification prompt.")
        return f"""
You searched for data based on the user's request but found no results. However, there are some potential issues:

**Potential Issues Detected:**
{chr(10).join(f"• {issue}" for issue in issues)}

**Your Task:**
1. Inform the user that no results were found
2. Explain possible reasons in friendly language
3. Ask clarifying questions
4. Offer to search with relaxed criteria

**User's Original Request:** {user_query}
"""

    def _generate_verification_prompt(self, sql_query: str) -> str:
        """Generate prompt for verifying legitimate zero results."""
        self.logger.debug("Generating verification prompt.")
        return """
You executed a count query that returned zero results. Before confirming this to the user, consider:

1. Is the time period in the future or recent past?
2. Are filters very specific?
3. Does the query look correct?

If legitimate: confidently report zero.
If suspicious: mention issues and offer to broaden the search.
"""

    def _generate_diagnostic_prompt(self, issues: list, has_related_data: bool) -> str:
        """Generate diagnostic prompt when query likely has issues."""
        self.logger.debug("Generating diagnostic prompt.")
        context = "I found that related data exists in the database" if has_related_data else "I couldn't find any related data"
        return f"""
You searched the database but found no matching records. {context}.

**Detected Issues:**
{chr(10).join(f"• {issue}" for issue in issues) if issues else "• Filters may be too specific or contain typos"}

**Your Task:**
1. Inform the user of no results
2. Suggest alternatives
3. Offer broader search
4. Stay helpful and solution-oriented
"""

