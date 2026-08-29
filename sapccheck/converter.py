def convert_sapc_response(data):
    """
    Chuyển SAPC JSON sang JSON tham chiếu
    """

    result = {
        "msisdn": str(data.get("MSISDN")),
        "packages": []
    }

    ad_map = {}

    for item in data.get("ADPersonalList", []):
        group_name = item.get("groupName")
        ad_map[group_name] = item

    for item in data.get("LUPersonalList", []):

        group_name = item.get("groupName")

        ad_info = ad_map.get(
            group_name,
            {}
        )

        result["packages"].append({
            "group_name": group_name,
            "package_name": item.get("description"),
            "register_date": item.get("subscriptionDate"),
            "expire_date": ad_info.get("expireDate")
        })

    return result