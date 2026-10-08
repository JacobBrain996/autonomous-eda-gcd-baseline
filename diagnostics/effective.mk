.PHONY: diagnostic-effective-vars
diagnostic-effective-vars:
	@python3 /diagnostic/prepare.py effective \
	  --lec '$(LEC_CHECK)' --sec '$(SEC_CHECK)' --executable '$(KEPLER_FORMAL_EXE)' \
	  --libs '$(LIB_FILES)' --remove-libs '$(REMOVE_LIBS_FOR_LEC)'
