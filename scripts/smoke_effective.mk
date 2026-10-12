.PHONY: smoke-effective-vars
smoke-effective-vars:
	@test "$(LEC_CHECK)" = 0 && test "$(SEC_CHECK)" = 0 && test "$(SKIP_CTS_REPAIR_TIMING)" = 0
	@printf 'LEC_CHECK=%s\nSEC_CHECK=%s\nSKIP_CTS_REPAIR_TIMING=%s\nDESIGN_CONFIG=%s\nPLATFORM=%s\nDESIGN_NAME=%s\nGDS_FINAL_FILE=%s\n' '$(LEC_CHECK)' '$(SEC_CHECK)' '$(SKIP_CTS_REPAIR_TIMING)' '$(DESIGN_CONFIG)' '$(PLATFORM)' '$(DESIGN_NAME)' '$(GDS_FINAL_FILE)'
