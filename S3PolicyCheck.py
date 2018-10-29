# coding:utf-8
import boto3
import json
            
# メイン
def lambda_handler(event, context):
    
    # DynamoDBからS3バケットポリシー内でアクセスを可能とするアカウントIDを取得
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('テーブル名')
    response = table.scan()
    list_accounts = []
    for res in response['Items']:
        list_accounts.append(res['account_id'])
    # DynamoDBからACLでアクセスを可能とするアカウントIDを取得
    table = dynamodb.Table('テーブル名')
    response = table.scan()
    list_grantee = []
    for res in response['Items']:
        list_grantee.append(res['grantee_id'])
    
    # s3取得
    s3 = boto3.client('s3')

    # 処理を実行
    # 本文用
    message = ""
    # バケット取得
    buckets = s3.list_buckets()
    for bucket in buckets['Buckets']:
        # バケット名出力
        print(bucket['Name'])
        try:
            # バケットのACL取得
            acl = s3.get_bucket_acl(Bucket=bucket['Name'])
            # ACLが設定されていない場合
            if len(acl['Grants']) == 0:
                print('アクセスコントロールリスト:閉めすぎ？')
            # ACLが設定されている場合
            else:
                # バケットの所有アカウントを例外リストに追加
                list_grantee.append(acl['Owner']['ID'])
                for grant in acl['Grants']:
                    if 'ID' in grant['Grantee']:
                        # 例外リストにないアカウントに許可設定があった場合は開けすぎ判定を出す
                        if not grant['Grantee']['ID'] in list_grantee:
                            print(grant['Grantee'])
                            print("開けすぎ？")
                            message += bucket['Name'] + '：未確認アカウントとの連携があります。：' + grant['Grantee']['DisplayName'] + '\n'
                    if 'URI' in grant['Grantee']:
                        # ログ配信出力グループ以外のURIに許可設定があった場合は開けすぎ判定を出す
                        if grant['Grantee']['URI'] != 'http://acs.amazonaws.com/groups/s3/LogDelivery':
                            print(grant['Grantee']['URI'])
                            print("開けすぎ？")
                            message += bucket['Name'] + '：未確認グループとの連携があります。：' + grant['Grantee']['URI'] + '\n'
                # 処理が終わったら例外リストから所有アカウントを削除
                list_grantee.pop()
            
            # バケットのバケットポリシーを取得
            policy = s3.get_bucket_policy(Bucket=bucket['Name'])
            policy_json = json.loads(policy['Policy'])
            for principal in policy_json['Statement']:
                if 'AWS' in principal['Principal']:
                    # 例外リストにないアカウントに許可設定があった場合は開けすぎ判定を出す
                    # 複数の許可設定がある場合は配列となるため、配列かどうか確認
                    if isinstance(principal['Principal']['AWS'],list):
                        for check in principal['Principal']['AWS']:
                            # check String型（例：arn:aws:iam::xxxxxxxxxxxx:root）
                            for account in list_accounts:
                                # checkの文字列の中に例外のアカウントで文字列が含まれていれば次のcheckへ
                                if account in check:
                                    break
                            # checkの文字列の中に例外のアカウントで文字列が含まれていなければ開けすぎ判定を出す
                            else:
                                print(check)
                                print('バケットポリシー:開けすぎ？')
                                message += bucket['Name'] + '：未確認アカウントとの連携があります。：' + check + '\n'
                    else:
                        for account in list_accounts:
                            if account in principal['Principal']['AWS']:
                                break
                        else:
                            print(principal['Principal']['AWS'])
                            print('バケットポリシー:開けすぎ？')
                            message += bucket['Name'] + '：未確認アカウントとの連携があります。：' + principal['Principal']['AWS'] + '\n'
                # Principalの許可設定が'*'の場合は開けすぎ判定を出す
                elif '*' in principal['Principal']:
                    print('*')
                    print('バケットポリシー:開けすぎ？')
                    message += bucket['Name'] + ':許可設定が広すぎます。\n'
        
        #バケットポリシーがない場合とOA環境からのアクセスしか受け付けないバケットの場合はエラーが発生するため、それ以外のエラーのみ吐き出すようにする
        except Exception as e:
            if str(e) == 'An error occurred (NoSuchBucketPolicy) when calling the GetBucketPolicy operation: The bucket policy does not exist':
                pass
            elif str(e) == 'An error occurred (AccessDenied) when calling the GetBucketAcl operation: Access Denied':
                pass
            else:
                print(e)
                
    return message

    if message:
        # 本文調整
        message = '以下のルール違反がありました。ご確認をお願いいたします。\n\n' + message
        # プリント
        print(message)