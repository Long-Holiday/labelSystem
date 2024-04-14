package com.example.labelMark.domain;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import java.io.Serializable;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Getter;
import lombok.Setter;

/**
 * <p>
 * 
 * </p>
 *
 * @author wh
 * @since 2024-04-12
 */
@Getter
@Setter
@TableName("role")
@ApiModel(value = "Role对象", description = "")
public class Role implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableField("id")
    private Integer id;

    @TableField("rolename")
    private String rolename;

    @TableField("rolecode")
    private Integer rolecode;


}
