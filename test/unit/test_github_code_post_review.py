"""
单元测试：验证 github_code.post_review_comment_to_pr 的行为
"""

import os
import sys
import types
import pytest

# 让测试能够导入 lambda 目录下的源码
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda'))

# 注入 awslambdaric 轻量替身，避免本地缺少该依赖时导入失败
if 'awslambdaric.lambda_runtime_log_utils' not in sys.modules:
	parent = types.ModuleType('awslambdaric')
	sub = types.ModuleType('awslambdaric.lambda_runtime_log_utils')
	class _JsonFormatter:
		def __init__(self, *a, **k):
			pass
		def format(self, record):
			return '{}'
	sub.JsonFormatter = _JsonFormatter
	sys.modules['awslambdaric'] = parent
	sys.modules['awslambdaric.lambda_runtime_log_utils'] = sub

import github_code


class DummyPR:
	def __init__(self):
		self.comments = []

	def create_issue_comment(self, body):
		self.comments.append(body)


class DummyRepository:
	def __init__(self):
		self.pull_numbers = []
		self.pull = DummyPR()

	def get_pull(self, number):
		self.pull_numbers.append(number)
		return self.pull


def test_post_review_comment_to_pr_accepts_str_pr_number():
	"""
	字符串类型的 PR 编号应自动转换为整数，并成功创建评论
	"""
	repo = DummyRepository()
	result = github_code.post_review_comment_to_pr(
		repo,
		"123",
		"https://example.com/report",
		[]
	)

	assert result is True
	assert repo.pull_numbers == [123], "PR 编号应被转换为整数后再调用 get_pull"
	assert len(repo.pull.comments) == 1
	assert "Code Review" in repo.pull.comments[0]


def test_post_review_comment_to_pr_invalid_pr_number():
	"""
	无法转换为整数的 PR 编号应返回 False，并且不调用 repository.get_pull
	"""
	repo = DummyRepository()
	result = github_code.post_review_comment_to_pr(
		repo,
		"not-a-number",
		"https://example.com/report",
		[]
	)

	assert result is False
	assert repo.pull_numbers == [], "无效编号不应调用 get_pull"


def test_build_pr_comment_with_realistic_report_data():
	report_url = "https://s3.example.com/report/auth-service/index.html"
	report_data = [
		{
			"rule": "AuthServer - Bug Review",
			"content": [
				{
					"title": "缓存中存储敏感信息可能导致安全风险",
					"content": (
						"在cacheUserLoginHistory方法中,将包含敏感信息的loginRecord直接存储在内存缓存中可能会导致安全风险。"
						"建议只缓存必要的非敏感信息,或者对敏感字段进行加密处理。"
					),
					"filepath": "auth-server/src/main/scala/.../LoginApiV4.scala @ 75-97"
				},
				{
					"title": "缓存未设置大小限制可能导致内存溢出",
					"content": (
						"userLoginHistoryCache 是一个无界的 mutable.Map,随着时间推移可能会无限增长,导致内存溢出。"
						"建议设置缓存大小限制或定期清理旧数据。"
					),
					"filepath": "auth-server/src/main/scala/.../LoginApiV4.scala @ 65-66"
				}
			]
		},
		{
			"rule": "AuthServer - Security Review",
			"content": [
				{
					"title": "使用共享可变状态可能导致并发问题",
					"content": "代码中使用了可变Map userLoginHistoryCache 作为共享状态来缓存用户登录历史,但没有进行同步处理。",
					"filepath": "auth-server/src/main/scala/.../LoginApiV4.scala @ 65-106"
				}
			]
		}
	]

	body = github_code.build_pr_comment(report_url, report_data)

	assert "AuthServer - Bug Review" in body
	assert "AuthServer - Security Review" in body
	assert "缓存中存储敏感信息可能导致安全风险" in body
	assert report_url in body
