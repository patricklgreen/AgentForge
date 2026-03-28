# ─── GitHub Actions OIDC Provider ────────────────────────────────────────────
#
# This resource allows GitHub Actions to authenticate to AWS without
# long-lived access keys (keyless authentication via OIDC).
#
# Only one OIDC provider per URL is allowed per AWS account.
# If you already have one, import it:
#   terraform import aws_iam_openid_connect_provider.github_actions \
#     arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com

resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # GitHub's OIDC thumbprints — these are stable and verified by AWS.
  # Reference: https://github.blog/changelog/2023-06-27-github-actions-oidc-support/
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]

  tags = { Name = "github-actions-oidc" }
}
