# Security

Report vulnerabilities to caci96@gmail.com. Do not open a public issue for them.

The package stores no credentials and sends none. The only deliberate relaxation is
`verify=False` on the two `amar.org.ir` workbook requests in `yfinance_ir/sources/sci.py`,
because that server omits its intermediate certificate; the payload is public statistics.
