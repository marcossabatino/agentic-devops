-- Cluster mode only: orders owns the effect; gateway has read-only authorization data.
GRANT USAGE ON SCHEMA public TO lab_orders;
GRANT SELECT ON jobs TO lab_orders;
GRANT SELECT, UPDATE (consumed_key) ON approvals TO lab_orders;
GRANT SELECT, INSERT ON tool_results TO lab_orders;
GRANT SELECT, INSERT, UPDATE ON orders_state TO lab_orders;
REVOKE UPDATE (consumed_key) ON approvals FROM lab_tools;
REVOKE INSERT ON tool_results FROM lab_tools;
REVOKE ALL ON orders_state FROM lab_tools;
